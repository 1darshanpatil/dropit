/**
 * Dynamically updates an HTML element to display a table of files selected for upload.
 * It constructs a table showing file names, types, and sizes.
 */
function updateFileList() {
    var input = document.getElementById('file-input');
    var output = document.getElementById('file-list');
    var children = "<table style='width: 100%; border-collapse: collapse;'>";
    children += "<tr><th>Name</th><th>Type</th><th>Size</th></tr>";

    for (var i = 0; i < input.files.length; i++) {
        let file = input.files.item(i);
        let size = formatSize(file.size); 
        let type = file.type || 'Unknown';  

        children += `<tr>
                        <td>${file.name}</td>
                        <td>${type}</td>
                        <td>${size}</td>
                    </tr>`;
    }
    children += "</table>";
    output.innerHTML = children;
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
