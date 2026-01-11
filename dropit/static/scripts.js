document.addEventListener('DOMContentLoaded', function () {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('fileInfo');
    const dragOverlay = document.getElementById('dragOverlay');

    // Open file browser when clicking on upload area
    uploadArea.addEventListener('click', function () {
        fileInput.click();
    });

    // Handle file selection
    fileInput.addEventListener('change', function () {
        updateFileList();
    });

    // Update file info display
    function updateFileList() {
        if (fileInput.files.length > 0) {
            if (fileInput.files.length === 1) {
                fileInfo.textContent = fileInput.files[0].name;
            } else {
                fileInfo.textContent = `${fileInput.files.length} files selected`;
            }
        } else {
            fileInfo.textContent = 'No files selected';
        }
    }

    // Drag and drop functionality
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, highlight, false);
        document.body.addEventListener(eventName, showOverlay, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, unhighlight, false);
        document.body.addEventListener(eventName, hideOverlay, false);
    });

    function highlight() {
        uploadArea.classList.add('dragover');
    }

    function unhighlight() {
        uploadArea.classList.remove('dragover');
    }

    function showOverlay() {
        dragOverlay.classList.add('active');
    }

    function hideOverlay() {
        dragOverlay.classList.remove('active');
    }

    // Handle file drop
    uploadArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        fileInput.files = dt.files;
        updateFileList();
    }

    // Initialize
    updateFileList();

    // Add active class to sort buttons when clicked
    const sortButtons = document.querySelectorAll('.sort-btn');
    sortButtons.forEach(button => {
        button.addEventListener('click', function () {
            sortButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
        });
    });
});

/**
* Dynamically updates an HTML element to display a table of files selected for upload.
* It constructs a table showing file names, types, and sizes.
*/
function updateFileList() {
    var input = document.getElementById('file-input');
    var output = document.getElementById('fileInfo');
    var children = "";

    if (input.files.length === 0) {
        output.textContent = 'No files selected';
        return;
    }

    if (input.files.length === 1) {
        output.textContent = input.files[0].name;
    } else {
        output.textContent = input.files.length + ' files selected';
    }
}

/**
* Converts file size from bytes to a more human-readable string format.
* @param {number} bytes - The file size in bytes.
* @return {string} The formatted file size with appropriate units.
*/
function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1024 ** 2) return (bytes / 1024).toFixed(2) + ' KB';
    else if (bytes < 1024 ** 3) return (bytes / 1024 ** 2).toFixed(2) + ' MB';
    else return (bytes / 1024 ** 3).toFixed(2) + ' GB';
}

/**
* Sorts an HTML table by the given column index, with optional handling for size columns.
* @param {number} n - The column index to sort by.
* @param {boolean} isSizeColumn - Indicates if the column contains file sizes for special handling.
*/
function sortTable(n, isSizeColumn = false) {
    var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
    table = document.getElementById("fileTable");
    switching = true;
    dir = "asc";

    while (switching) {
        switching = false;
        rows = table.rows;

        for (i = 1; i < (rows.length - 1); i++) {
            shouldSwitch = false;
            x = rows[i].getElementsByTagName("TD")[n];
            y = rows[i + 1].getElementsByTagName("TD")[n];
            var xVal = isSizeColumn ? convertToBytes(x.innerHTML) : x.innerHTML.toLowerCase();
            var yVal = isSizeColumn ? convertToBytes(y.innerHTML) : y.innerHTML.toLowerCase();

            if (dir == "asc") {
                if (xVal > yVal) {
                    shouldSwitch = true;
                    break;
                }
            } else if (dir == "desc") {
                if (xVal < yVal) {
                    shouldSwitch = true;
                    break;
                }
            }
        }
        if (shouldSwitch) {
            rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
            switching = true;
            switchcount++;
        } else {
            if (switchcount == 0 && dir == "asc") {
                dir = "desc";
                switching = true;
            }
        }
    }

    // Update the visible file list
    updateVisibleFileList();
}

/**
* Updates the visible file list after sorting
*/
function updateVisibleFileList() {
    const table = document.getElementById('fileTable');
    const tbody = table.querySelector('tbody');
    const fileList = document.getElementById('fileList');

    // Clear current list
    fileList.innerHTML = '';

    // Get all rows except the header
    const rows = Array.from(tbody.querySelectorAll('tr'));

    // Create new list items
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        const downloadLink = row.querySelector('.dropdown-content a');
        const deleteLink = row.querySelector('.dropdown-content a:last-child');

        const listItem = document.createElement('li');
        listItem.className = 'file-item';

        listItem.innerHTML = `
<div class="file-info">
<div class="file-name">${cells[0].textContent}</div>
<div class="file-meta">
<span>${cells[1].textContent}</span>
<span>${cells[2].textContent}</span>
</div>
</div>
<div class="file-actions">
<a href="${downloadLink ? downloadLink.href : '#'}" class="action-chip download" title="Download">
  <span class="icon" aria-hidden="true">⬇️</span>
  <span class="label">Download</span>
</a>
<a href="${deleteLink ? deleteLink.href : '#'}" class="action-chip delete" title="Delete">
  <span class="icon" aria-hidden="true">🗑️</span>
  <span class="label">Delete</span>
</a>
</div>
`;

        fileList.appendChild(listItem);
    });
}

/**
* Converts a human-readable file size string back to bytes for numerical comparison.
* @param {string} sizeStr - The size string to convert (e.g., "2.5 MB").
* @return {number} The size in bytes.
*/
function convertToBytes(sizeStr) {
    const units = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"];
    const size = parseFloat(sizeStr);
    const unit = sizeStr.replace(/[.\d\s]/g, '').toUpperCase();
    const exponent = units.indexOf(unit);
    return size * Math.pow(1024, exponent);
}
