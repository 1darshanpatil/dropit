document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-input');
    const uploadForm = document.getElementById('uploadForm');
    const uploadButton = document.getElementById('uploadButton');
    const addMoreFilesButton = document.getElementById('addMoreFilesButton');
    const clearFilesButton = document.getElementById('clearFilesButton');
    const fileInfo = document.getElementById('fileInfo');
    const fileSearch = document.getElementById('fileSearch');
    const placesPane = document.getElementById('placesPane');
    const togglePlacesButton = document.getElementById('togglePlacesButton');
    const filePane = document.getElementById('filePane');
    const fileList = document.getElementById('fileList');
    const mobileSort = document.getElementById('mobileSort');
    const selectAllFiles = document.getElementById('selectAllFiles');
    const selectionBar = document.getElementById('selectionBar');
    const selectedCount = document.getElementById('selectedCount');
    const emptyState = document.getElementById('emptyState');
    const dropIndicator = document.getElementById('dropIndicator');
    const statusText = document.getElementById('statusText');
    const statusMessage = document.getElementById('statusMessage');
    const imagePreviewDialog = document.getElementById('imagePreviewDialog');
    const previewTitle = document.getElementById('previewTitle');
    const previewImage = document.getElementById('previewImage');
    const previewError = document.getElementById('previewError');
    const previewDownload = document.getElementById('previewDownload');
    const batchDownloadForm = document.getElementById('batchDownloadForm');
    const messageDialog = document.getElementById('messageDialog');
    const messageTitle = document.getElementById('messageTitle');
    const messageBody = document.getElementById('messageBody');
    const messageCancel = document.getElementById('messageCancel');
    const messageConfirm = document.getElementById('messageConfirm');
    const contextMenu = document.getElementById('contextMenu');
    const contextItemGroup = contextMenu.querySelector('[data-context-group="item"]');
    const contextPaneGroup = contextMenu.querySelector('[data-context-group="pane"]');
    const contextOpenItem = contextMenu.querySelector('[data-context-command="open"]');
    const contextSelectItem = contextMenu.querySelector('[data-context-command="select"]');
    const contextDownloadItem = contextMenu.querySelector('[data-context-command="download"]');
    const contextDeleteItem = contextMenu.querySelector('[data-context-command="delete"]');
    const homeLink = document.querySelector('.place-link');
    const upButton = document.querySelector('.tool-button[data-command="up"]');
    const rows = Array.from(document.querySelectorAll('.file-row'));
    const placeButtons = Array.from(document.querySelectorAll('button[data-filter]'));
    const menuButtons = Array.from(document.querySelectorAll('[data-menu-button]'));
    const columnButtons = Array.from(document.querySelectorAll('[data-sort]'));
    const viewButtons = Array.from(document.querySelectorAll('[data-view]'));
    let initialStatusText = statusText.textContent;

    let activeFilter = 'all';
    let sortKey = 'name';
    let sortDirection = 'asc';
    let lastSelectedRow = null;
    let queuedFiles = [];
    let dragDepth = 0;
    const maxUploadBytes = Number.parseInt(document.body.dataset.maxUpload, 10) || 0;
    const maxUploadLabel = document.body.dataset.maxUploadLabel || '';
    let contextRow = null;
    let longPressOpenedAt = 0;
    let longPressTimer = null;
    let longPressPoint = null;
    let longPressFired = false;

    const pluralize = (count, word) => `${count} ${count === 1 ? word : `${word}s`}`;

    const bytesFromSize = (row) => Number.parseInt(row.dataset.sizeBytes, 10) || 0;

    const formatBytes = (bytes) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
        if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
        return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
    };

    const visibleRows = () => Array.from(fileList.querySelectorAll('.file-row')).filter((row) => !row.hidden);
    const selectedRows = () => visibleRows().filter((row) => row.querySelector('.file-select').checked);
    const selectedFiles = () => selectedRows().filter((row) => row.dataset.kind === 'file');

    const focusRow = (row) => {
        if (!row) return;
        rows.forEach((item) => { item.tabIndex = item === row ? 0 : -1; });
        row.focus();
    };

    const ensureRovingTabStop = () => {
        const visible = visibleRows();
        const current = visible.find((row) => row.tabIndex === 0);
        if (current) return;
        rows.forEach((row) => { row.tabIndex = row === visible[0] ? 0 : -1; });
    };

    const setStatus = (message) => {
        statusMessage.textContent = message;
    };

    // In-app dialogs: the browser's own confirm()/alert() look like a security prompt
    // rather than part of the app, and they block the whole page while open.
    let resolveDialog = null;

    const settleDialog = (answer) => {
        if (!resolveDialog) return;
        const resolve = resolveDialog;
        resolveDialog = null;
        if (messageDialog.open) messageDialog.close();
        resolve(answer);
    };

    const openDialog = ({ title, message, confirmLabel = 'OK', cancelLabel = null, danger = false }) => {
        settleDialog(false);
        messageTitle.textContent = title;
        messageBody.textContent = message;
        messageConfirm.textContent = confirmLabel;
        messageConfirm.classList.toggle('danger-selection-action', danger);
        messageCancel.hidden = !cancelLabel;
        if (cancelLabel) messageCancel.textContent = cancelLabel;

        if (typeof messageDialog.showModal === 'function') {
            messageDialog.showModal();
        } else {
            messageDialog.setAttribute('open', '');
        }
        messageConfirm.focus();

        return new Promise((resolve) => { resolveDialog = resolve; });
    };

    const askToConfirm = (message, confirmLabel, danger = false) =>
        openDialog({ title: confirmLabel.replace(/…$/, ''), message, confirmLabel, cancelLabel: 'Cancel', danger });

    const showNotice = (title, message) => openDialog({ title, message });

    messageConfirm.addEventListener('click', () => settleDialog(true));
    messageCancel.addEventListener('click', () => settleDialog(false));
    messageDialog.addEventListener('cancel', (event) => { event.preventDefault(); settleDialog(false); });
    messageDialog.addEventListener('close', () => settleDialog(false));

    const closeContextMenu = () => {
        if (contextMenu.hidden) return;
        contextMenu.hidden = true;
        contextRow = null;
    };

    const closeMenus = (exceptButton = null) => {
        closeContextMenu();
        menuButtons.forEach((button) => {
            if (button === exceptButton) return;
            button.setAttribute('aria-expanded', 'false');
            button.nextElementSibling.hidden = true;
        });
    };

    const setRowSelected = (row, selected) => {
        row.querySelector('.file-select').checked = selected;
        row.classList.toggle('is-selected', selected);
        row.setAttribute('aria-selected', String(selected));
    };

    const updateSelectionState = () => {
        const selected = selectedRows();
        const files = selectedFiles();
        const visible = visibleRows();

        rows.forEach((row) => {
            const checked = row.querySelector('.file-select').checked;
            row.classList.toggle('is-selected', checked);
            row.setAttribute('aria-selected', String(checked));
        });

        selectedCount.textContent = `${pluralize(selected.length, 'item')} selected`;
        selectionBar.hidden = selected.length === 0;
        // Checkboxes only earn their place once something is actually selected.
        filePane.dataset.selecting = String(selected.length > 0);
        selectAllFiles.hidden = selected.length === 0;
        selectAllFiles.checked = visible.length > 0 && visible.every((row) => row.querySelector('.file-select').checked);
        selectAllFiles.indeterminate = visible.some((row) => row.querySelector('.file-select').checked) && !selectAllFiles.checked;

        document.querySelectorAll('[data-command="open-selected"]').forEach((button) => {
            button.disabled = selected.length !== 1;
        });
        document.querySelectorAll('[data-command="download-selected"]').forEach((button) => {
            button.disabled = files.length === 0;
        });
        document.querySelectorAll('[data-command="delete-selected"]').forEach((button) => {
            button.disabled = selected.length === 0;
        });

        if (selected.length) {
            statusText.textContent = `${pluralize(selected.length, 'item')} selected; ${pluralize(files.length, 'file')}`;
        } else {
            const filtered = activeFilter !== 'all' || Boolean(fileSearch.value.trim());
            statusText.textContent = filtered
                ? `${visible.length} of ${pluralize(rows.length, 'item')} shown`
                : initialStatusText;
        }
    };

    const clearSelection = () => {
        rows.forEach((row) => setRowSelected(row, false));
        lastSelectedRow = null;
        updateSelectionState();
    };

    const selectAllVisible = () => {
        visibleRows().forEach((row) => setRowSelected(row, true));
        updateSelectionState();
    };

    const updateSortControls = () => {
        columnButtons.forEach((button) => {
            const active = button.dataset.sort === sortKey;
            button.classList.toggle('is-sorted', active);
            button.dataset.direction = active ? sortDirection : '';
            button.setAttribute('aria-sort', active ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none');
        });

        const option = `${sortKey}-${sortDirection}`;
        if (mobileSort.querySelector(`option[value="${option}"]`)) mobileSort.value = option;
    };

    const sortRows = () => {
        rows
            .slice()
            .sort((first, second) => {
                if (first.dataset.kind !== second.dataset.kind) return first.dataset.kind === 'folder' ? -1 : 1;

                const multiplier = sortDirection === 'asc' ? 1 : -1;
                if (sortKey === 'size') return (bytesFromSize(first) - bytesFromSize(second)) * multiplier;

                return first.dataset[sortKey].localeCompare(second.dataset[sortKey], undefined, {
                    numeric: true,
                    sensitivity: 'base'
                }) * multiplier;
            })
            .forEach((row) => fileList.appendChild(row));

        updateSortControls();
    };

    const applyFileView = () => {
        closeContextMenu();
        const searchTerm = fileSearch.value.trim().toLocaleLowerCase();

        rows.forEach((row) => {
            const matchesType = activeFilter === 'all' || row.dataset.category === activeFilter;
            const matchesSearch = !searchTerm || `${row.dataset.name} ${row.dataset.type}`.includes(searchTerm);
            row.hidden = !(matchesType && matchesSearch);
            if (row.hidden) setRowSelected(row, false);
        });

        if (lastSelectedRow?.hidden) lastSelectedRow = null;

        sortRows();
        ensureRovingTabStop();

        const visible = visibleRows();
        const filtered = activeFilter !== 'all' || Boolean(searchTerm);
        emptyState.hidden = visible.length > 0;
        if (!visible.length) {
            emptyState.querySelector('p').textContent = rows.length && filtered
                ? 'No files or folders match this view.'
                : 'This folder is empty.';
        }

        updateSelectionState();
    };

    const setFilter = (filter) => {
        activeFilter = filter;
        placeButtons.forEach((button) => button.classList.toggle('is-active', button.dataset.filter === filter));
        placesPane.classList.remove('is-open');
        togglePlacesButton.setAttribute('aria-expanded', 'false');
        applyFileView();
    };

    const setView = (view, remember = true) => {
        const normalized = view === 'icons' ? 'icons' : 'details';
        filePane.dataset.view = normalized;

        viewButtons.forEach((button) => {
            const active = button.dataset.view === normalized;
            button.classList.toggle('is-active', active);
            button.setAttribute('aria-pressed', String(active));
        });

        const detailsItem = document.querySelector('[data-command="details-view"]');
        const iconsItem = document.querySelector('[data-command="icons-view"]');
        detailsItem.classList.toggle('is-checked', normalized === 'details');
        iconsItem.classList.toggle('is-checked', normalized === 'icons');
        detailsItem.setAttribute('aria-checked', String(normalized === 'details'));
        iconsItem.setAttribute('aria-checked', String(normalized === 'icons'));

        if (remember) {
            try {
                window.localStorage.setItem('dropit-file-view', normalized);
            } catch (_error) {
                // View switching still works when browser storage is unavailable.
            }
        }
    };

    const replaceQueuedFiles = (files) => {
        const unique = new Map();
        files.forEach((file) => unique.set(`${file.name}:${file.size}:${file.lastModified}`, file));
        queuedFiles = Array.from(unique.values());

        try {
            const transfer = new DataTransfer();
            queuedFiles.forEach((file) => transfer.items.add(file));
            fileInput.files = transfer.files;
        } catch (_error) {
            queuedFiles = Array.from(fileInput.files);
        }

        if (!queuedFiles.length) {
            uploadForm.hidden = true;
            uploadButton.disabled = true;
            fileInfo.textContent = 'No files selected';
            return;
        }

        const totalBytes = queuedFiles.reduce((sum, file) => sum + file.size, 0);
        const overLimit = maxUploadBytes > 0 && totalBytes > maxUploadBytes;

        fileInfo.textContent = overLimit
            ? `${pluralize(queuedFiles.length, 'file')} selected (${formatBytes(totalBytes)}) — over the ${maxUploadLabel} limit`
            : `${pluralize(queuedFiles.length, 'file')} ready for this folder (${formatBytes(totalBytes)})`;
        uploadForm.hidden = false;
        uploadButton.disabled = overLimit;

        if (overLimit) {
            // Sending it anyway just drops the connection mid-transfer, which looks like a crash.
            setStatus(`Selection is larger than the ${maxUploadLabel} upload limit`);
            showNotice(
                'Too large to upload',
                `These files add up to ${formatBytes(totalBytes)}, over this server's ${maxUploadLabel} limit.\n\n`
                + 'Remove some files, or restart dropit with a bigger --maxsize.',
            );
            return;
        }

        setStatus('Files ready to upload');
    };

    const clearUploadFiles = () => {
        queuedFiles = [];
        fileInput.value = '';
        replaceQueuedFiles([]);
        setStatus('Upload cleared');
    };

    const showImagePreview = (row) => {
        const name = row.querySelector('.file-name').textContent;
        previewTitle.textContent = name;
        previewImage.hidden = false;
        previewError.hidden = true;
        previewImage.src = row.dataset.openUrl;
        previewImage.alt = `Preview of ${name}`;
        previewDownload.href = row.dataset.downloadUrl;
        previewDownload.setAttribute('download', name);

        if (typeof imagePreviewDialog.showModal === 'function') {
            imagePreviewDialog.showModal();
        } else {
            imagePreviewDialog.setAttribute('open', '');
        }
    };

    const closeImagePreview = () => {
        if (typeof imagePreviewDialog.close === 'function' && imagePreviewDialog.open) {
            imagePreviewDialog.close();
        } else {
            imagePreviewDialog.removeAttribute('open');
        }
        previewImage.removeAttribute('src');
        previewImage.hidden = false;
        previewError.hidden = true;
    };

    const openRow = (row) => {
        if (!row) return;
        if (row.dataset.previewable === 'true') {
            showImagePreview(row);
            return;
        }
        window.location.assign(row.dataset.openUrl);
    };

    const downloadRows = (rowsToDownload) => {
        const files = rowsToDownload.filter((row) => row.dataset.kind === 'file');
        if (!files.length) return;

        batchDownloadForm.replaceChildren();
        files.forEach((row) => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'paths';
            input.value = row.dataset.path;
            batchDownloadForm.appendChild(input);
        });
        HTMLFormElement.prototype.submit.call(batchDownloadForm);

        setStatus(files.length === 1 ? 'Downloading selected file…' : `Preparing ${pluralize(files.length, 'file')} as a ZIP…`);
    };

    const refreshFolderTotals = () => {
        const folders = rows.filter((row) => row.dataset.kind === 'folder').length;
        initialStatusText = `${pluralize(folders, 'folder')}, ${pluralize(rows.length - folders, 'file')}`;

        const counted = {};
        placeButtons.forEach((button) => { counted[button.dataset.filter] = 0; });
        rows.forEach((row) => { counted[row.dataset.category] = (counted[row.dataset.category] || 0) + 1; });
        counted.all = rows.length;
        Object.entries(counted).forEach(([category, count]) => {
            const output = document.querySelector(`[data-count-for="${category}"]`);
            if (output) output.textContent = count;
        });
    };

    const deleteRows = async (selected) => {
        if (!selected.length) return;

        const folderCount = selected.filter((row) => row.dataset.kind === 'folder').length;
        const description = selected.length === 1
            ? `“${selected[0].dataset.displayName}”`
            : `${pluralize(selected.length, 'item')}`;
        const note = folderCount ? '\n\nFolders must be empty before they can be deleted.' : '';

        const confirmed = await askToConfirm(
            `Permanently delete ${description}? This cannot be undone.${note}`,
            'Delete',
            true,
        );
        if (!confirmed) return;

        setStatus(`Deleting ${pluralize(selected.length, 'item')}…`);
        const results = await Promise.all(selected.map(async (row) => {
            try {
                const response = await fetch(row.dataset.deleteUrl, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                const data = await response.json().catch(() => ({}));
                if (response.ok) return { row, error: null };
                return { row, error: data.error || `Could not delete ${row.dataset.displayName}` };
            } catch (_error) {
                return { row, error: `Could not delete ${row.dataset.displayName}` };
            }
        }));

        // Drop the rows that really went away rather than reloading the whole page,
        // which loses the scroll position and flashes the whole list.
        const removed = results.filter((result) => !result.error);
        removed.forEach(({ row }) => {
            setRowSelected(row, false);
            row.remove();
            const index = rows.indexOf(row);
            if (index >= 0) rows.splice(index, 1);
        });
        if (lastSelectedRow && !lastSelectedRow.isConnected) lastSelectedRow = null;

        refreshFolderTotals();
        applyFileView();

        const errors = results.filter((result) => result.error).map((result) => result.error);
        if (errors.length) {
            await showNotice(
                errors.length === 1 ? 'Could not delete' : `Could not delete ${errors.length} items`,
                errors.join('\n'),
            );
        }
        setStatus(removed.length
            ? `Deleted ${pluralize(removed.length, 'item')}`
            : 'Nothing was deleted');
    };

    // Right-click (or a long press on touch) drives the item actions; a plain left click only
    // moves focus, so nothing is ever selected by accident while browsing.
    const contextTargets = () => {
        if (!contextRow) return [];
        const selected = selectedRows();
        return selected.length > 1 && selected.includes(contextRow) ? selected : [contextRow];
    };

    const contextItems = () => {
        const group = contextItemGroup.hidden ? contextPaneGroup : contextItemGroup;
        return Array.from(group.querySelectorAll('button:not(:disabled)'));
    };

    const placeContextMenu = (x, y) => {
        contextMenu.hidden = false;
        contextMenu.style.visibility = 'hidden';
        contextMenu.style.left = '0px';
        contextMenu.style.top = '0px';

        const { width, height } = contextMenu.getBoundingClientRect();
        const left = Math.max(4, Math.min(x, window.innerWidth - width - 4));
        const top = Math.max(4, Math.min(y, window.innerHeight - height - 4));

        contextMenu.style.left = `${left}px`;
        contextMenu.style.top = `${top}px`;
        contextMenu.style.visibility = '';
        contextMenu.focus({ preventScroll: true });
    };

    const openContextMenu = (x, y, row) => {
        closeMenus();
        contextRow = row || null;
        contextItemGroup.hidden = !contextRow;
        contextPaneGroup.hidden = Boolean(contextRow);

        if (contextRow) {
            const targets = contextTargets();
            const files = targets.filter((item) => item.dataset.kind === 'file');
            const many = targets.length > 1;
            const allSelected = targets.every((item) => item.querySelector('.file-select').checked);
            const label = many ? ` ${pluralize(targets.length, 'item')}` : '';

            contextOpenItem.hidden = many;
            contextOpenItem.textContent = contextRow.dataset.kind === 'folder' ? 'Open Folder' : 'Open';
            contextSelectItem.textContent = `${allSelected ? 'Deselect' : 'Select'}${label}`;
            contextDownloadItem.textContent = files.length > 1
                ? `Download ${pluralize(files.length, 'file')} (ZIP)`
                : 'Download';
            contextDownloadItem.disabled = files.length === 0;
            contextDeleteItem.textContent = `Delete${label}…`;
        }

        placeContextMenu(x, y);
    };

    const contextPoint = (event, fallback) => {
        // Keyboard-invoked menus (Shift+F10, the Menu key) report no useful coordinates.
        if (event.clientX > 0 || event.clientY > 0) return [event.clientX, event.clientY];
        const rect = (fallback || filePane).getBoundingClientRect();
        return [rect.left + 14, rect.top + 14];
    };

    const runContextCommand = (command, targets) => {
        if (!targets.length) return;

        switch (command) {
            case 'open':
                openRow(targets[0]);
                break;
            case 'select': {
                const select = !targets.every((row) => row.querySelector('.file-select').checked);
                targets.forEach((row) => setRowSelected(row, select));
                lastSelectedRow = select ? targets[targets.length - 1] : null;
                updateSelectionState();
                setStatus(select
                    ? `${pluralize(targets.length, 'item')} selected`
                    : `${pluralize(targets.length, 'item')} deselected`);
                break;
            }
            case 'download':
                downloadRows(targets);
                break;
            case 'delete':
                deleteRows(targets);
                break;
            default:
                break;
        }
    };

    const runCommand = (command) => {
        switch (command) {
            case 'upload':
                fileInput.click();
                break;
            case 'open-selected':
                openRow(selectedRows()[0]);
                break;
            case 'download-selected':
                downloadRows(selectedFiles());
                break;
            case 'delete-selected':
                deleteRows(selectedRows());
                break;
            case 'reload':
                window.location.reload();
                break;
            case 'select-all':
                selectAllVisible();
                break;
            case 'clear-selection':
                clearSelection();
                break;
            case 'focus-search':
                fileSearch.focus();
                fileSearch.select();
                break;
            case 'details-view':
                setView('details');
                break;
            case 'icons-view':
                setView('icons');
                break;
            case 'history-back':
                window.history.back();
                break;
            case 'history-forward':
                window.history.forward();
                break;
            case 'up':
                if (upButton?.dataset.parentUrl) window.location.assign(upButton.dataset.parentUrl);
                break;
            case 'home':
                window.location.assign(homeLink.href);
                break;
            default:
                break;
        }
    };

    rows.forEach((row) => {
        const checkbox = row.querySelector('.file-select');

        checkbox.addEventListener('change', () => {
            setRowSelected(row, checkbox.checked);
            lastSelectedRow = row;
            updateSelectionState();
        });

        row.addEventListener('focus', () => {
            rows.forEach((item) => { item.tabIndex = item === row ? 0 : -1; });
        });

        row.addEventListener('click', (event) => {
            if (event.target.closest('a, button, input')) return;

            if (event.shiftKey) {
                // Extend from the previous anchor, exactly like a desktop file manager.
                const visible = visibleRows();
                const anchor = lastSelectedRow && !lastSelectedRow.hidden ? lastSelectedRow : row;
                if (!event.ctrlKey && !event.metaKey) rows.forEach((item) => setRowSelected(item, false));
                const [start, end] = [visible.indexOf(anchor), visible.indexOf(row)].sort((a, b) => a - b);
                if (start >= 0) visible.slice(start, end + 1).forEach((item) => setRowSelected(item, true));
                lastSelectedRow = row;
            } else if (event.ctrlKey || event.metaKey) {
                setRowSelected(row, !checkbox.checked);
                lastSelectedRow = row;
            }
            // A plain click deliberately selects nothing: use the checkbox, or right-click
            // (long-press on touch) and choose Select.

            focusRow(row);
            updateSelectionState();
        });

        row.addEventListener('dblclick', (event) => {
            if (event.target.closest('a, button, input')) return;
            openRow(row);
        });

        row.addEventListener('keydown', (event) => {
            if (event.target !== row) return;
            if (event.key === ' ') {
                event.preventDefault();
                setRowSelected(row, !checkbox.checked);
                lastSelectedRow = row;
                updateSelectionState();
            } else if (event.key === 'Enter') {
                event.preventDefault();
                openRow(row);
            } else if (['ArrowUp', 'ArrowLeft', 'ArrowDown', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
                event.preventDefault();
                const visible = visibleRows();
                const currentIndex = visible.indexOf(row);
                let nextIndex = currentIndex;
                if (event.key === 'Home') nextIndex = 0;
                if (event.key === 'End') nextIndex = visible.length - 1;
                if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') nextIndex = Math.max(0, currentIndex - 1);
                if (event.key === 'ArrowDown' || event.key === 'ArrowRight') nextIndex = Math.min(visible.length - 1, currentIndex + 1);
                focusRow(visible[nextIndex]);
            }
        });

        row.querySelector('[data-preview-image]')?.addEventListener('click', () => showImagePreview(row));
    });

    const nativeMenuZone = (target) => Boolean(
        target.closest('.file-list-heading, .selection-strip, .mobile-pane-tools')
    );

    const cancelLongPress = () => {
        if (longPressTimer === null) return;
        window.clearTimeout(longPressTimer);
        longPressTimer = null;
    };

    filePane.addEventListener('contextmenu', (event) => {
        if (nativeMenuZone(event.target)) return;
        event.preventDefault();
        // Touch browsers fire this right after our own long-press handler; ignore the echo.
        if (Date.now() - longPressOpenedAt < 900) return;
        const row = event.target.closest('.file-row');
        const [x, y] = contextPoint(event, row);
        openContextMenu(x, y, row);
    });

    filePane.addEventListener('touchstart', (event) => {
        cancelLongPress();
        // A gesture that never produced a click must not swallow the next real tap.
        longPressFired = false;
        if (event.touches.length !== 1 || nativeMenuZone(event.target)) return;
        if (event.target.closest('input, .thumbnail-button')) return;

        const touch = event.touches[0];
        const row = event.target.closest('.file-row');
        longPressPoint = { x: touch.clientX, y: touch.clientY };
        longPressTimer = window.setTimeout(() => {
            longPressTimer = null;
            longPressFired = true;
            longPressOpenedAt = Date.now();
            openContextMenu(longPressPoint.x, longPressPoint.y, row);
        }, 500);
    }, { passive: true });

    filePane.addEventListener('touchmove', (event) => {
        if (longPressTimer === null || !longPressPoint) return;
        const touch = event.touches[0];
        if (!touch) return;
        if (Math.abs(touch.clientX - longPressPoint.x) > 10 || Math.abs(touch.clientY - longPressPoint.y) > 10) {
            cancelLongPress();
        }
    }, { passive: true });

    filePane.addEventListener('touchend', cancelLongPress);
    filePane.addEventListener('touchcancel', cancelLongPress);

    // Swallow the tap that a long press would otherwise deliver to the row underneath.
    filePane.addEventListener('click', (event) => {
        if (!longPressFired) return;
        longPressFired = false;
        event.preventDefault();
        event.stopPropagation();
    }, true);

    // Clicking empty space in the pane clears the selection, as in a desktop file manager.
    filePane.addEventListener('click', (event) => {
        if (event.target.closest('.file-row, .file-list-heading, .selection-strip, .mobile-pane-tools')) return;
        if (event.target.closest('a, button, input, label, select')) return;
        if (selectedRows().length) clearSelection();
    });

    contextMenu.addEventListener('click', (event) => {
        const button = event.target.closest('[data-context-command]');
        if (!button || button.disabled) return;
        const command = button.dataset.contextCommand;
        const targets = contextTargets();
        closeContextMenu();
        runContextCommand(command, targets);
    });

    contextMenu.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            event.preventDefault();
            const row = contextRow;
            closeContextMenu();
            focusRow(row);
            return;
        }

        if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const items = contextItems();
        if (!items.length) return;
        const currentIndex = items.indexOf(document.activeElement);
        let nextIndex = 0;
        if (event.key === 'End') nextIndex = items.length - 1;
        if (event.key === 'ArrowDown') nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % items.length;
        if (event.key === 'ArrowUp') nextIndex = currentIndex < 0 ? items.length - 1 : (currentIndex - 1 + items.length) % items.length;
        items[nextIndex]?.focus();
    });

    filePane.addEventListener('scroll', closeContextMenu, { passive: true });
    window.addEventListener('resize', closeContextMenu);

    document.querySelectorAll('.thumbnail-button img').forEach((image) => {
        const showFallback = () => image.closest('.thumbnail-button')?.classList.add('is-broken');
        image.addEventListener('error', showFallback);
        if (image.complete && image.naturalWidth === 0) showFallback();
    });

    const counts = {};
    placeButtons.forEach((button) => { counts[button.dataset.filter] = 0; });
    rows.forEach((row) => { counts[row.dataset.category] = (counts[row.dataset.category] || 0) + 1; });
    counts.all = rows.length;
    Object.entries(counts).forEach(([category, count]) => {
        const output = document.querySelector(`[data-count-for="${category}"]`);
        if (output) output.textContent = count;
    });

    menuButtons.forEach((button) => {
        button.addEventListener('click', (event) => {
            event.stopPropagation();
            const popup = button.nextElementSibling;
            const opening = popup.hidden;
            closeMenus(button);
            popup.hidden = !opening;
            button.setAttribute('aria-expanded', String(opening));
            if (opening) popup.querySelector('button:not(:disabled)')?.focus();
        });

        button.addEventListener('keydown', (event) => {
            if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
            event.preventDefault();
            const popup = button.nextElementSibling;
            closeMenus(button);
            popup.hidden = false;
            button.setAttribute('aria-expanded', 'true');
            const items = Array.from(popup.querySelectorAll('button:not(:disabled)'));
            (event.key === 'ArrowUp' ? items.at(-1) : items[0])?.focus();
        });

        button.nextElementSibling.addEventListener('keydown', (event) => {
            const popup = button.nextElementSibling;
            const items = Array.from(popup.querySelectorAll('button:not(:disabled)'));
            const currentIndex = items.indexOf(document.activeElement);

            if (['Enter', ' ', 'Spacebar'].includes(event.key) && currentIndex >= 0) {
                event.preventDefault();
                items[currentIndex].click();
                return;
            }

            if (event.key === 'Escape') {
                event.preventDefault();
                closeMenus();
                button.focus();
                return;
            }

            if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            let nextIndex = currentIndex;
            if (event.key === 'Home') nextIndex = 0;
            if (event.key === 'End') nextIndex = items.length - 1;
            if (event.key === 'ArrowDown') nextIndex = (currentIndex + 1 + items.length) % items.length;
            if (event.key === 'ArrowUp') nextIndex = (currentIndex - 1 + items.length) % items.length;
            items[nextIndex]?.focus();
        });
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.context-menu')) closeContextMenu();

        const commandButton = event.target.closest('[data-command]');
        if (commandButton && !commandButton.disabled) {
            const ownerMenuButton = commandButton.closest('.menu')?.querySelector('[data-menu-button]');
            runCommand(commandButton.dataset.command);
            closeMenus();
            if (ownerMenuButton && document.activeElement === commandButton) ownerMenuButton.focus();
        } else if (!event.target.closest('.menu')) {
            closeMenus();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            const openMenuButton = menuButtons.find((button) => button.getAttribute('aria-expanded') === 'true');
            closeMenus();
            openMenuButton?.focus();
            placesPane.classList.remove('is-open');
            togglePlacesButton.setAttribute('aria-expanded', 'false');
            if (imagePreviewDialog.open) closeImagePreview();
        }

        const editing = event.target instanceof Element && event.target.matches('input, textarea, select');
        if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === 'a' && !editing) {
            event.preventDefault();
            selectAllVisible();
        }
        if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === 'f') {
            event.preventDefault();
            fileSearch.focus();
            fileSearch.select();
        }
    });

    placeButtons.forEach((button) => button.addEventListener('click', () => setFilter(button.dataset.filter)));
    viewButtons.forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));

    columnButtons.forEach((button) => {
        button.addEventListener('click', () => {
            if (sortKey === button.dataset.sort) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                sortKey = button.dataset.sort;
                sortDirection = sortKey === 'size' ? 'desc' : 'asc';
            }
            sortRows();
            setStatus(`Sorted by ${sortKey}, ${sortDirection === 'asc' ? 'ascending' : 'descending'}`);
        });
    });

    mobileSort.addEventListener('change', () => {
        [sortKey, sortDirection] = mobileSort.value.split('-');
        sortRows();
    });

    fileSearch.addEventListener('input', applyFileView);

    selectAllFiles.addEventListener('change', () => {
        visibleRows().forEach((row) => setRowSelected(row, selectAllFiles.checked));
        updateSelectionState();
    });

    togglePlacesButton.addEventListener('click', () => {
        const open = !placesPane.classList.contains('is-open');
        placesPane.classList.toggle('is-open', open);
        togglePlacesButton.setAttribute('aria-expanded', String(open));
    });

    fileInput.addEventListener('change', () => replaceQueuedFiles([...queuedFiles, ...Array.from(fileInput.files)]));
    addMoreFilesButton.addEventListener('click', () => fileInput.click());
    clearFilesButton.addEventListener('click', clearUploadFiles);

    uploadForm.addEventListener('submit', (event) => {
        if (!fileInput.files.length) {
            event.preventDefault();
            return;
        }
        uploadButton.disabled = true;
        uploadButton.textContent = 'Uploading…';
        setStatus('Uploading files into this folder…');
    });

    document.addEventListener('dragenter', (event) => {
        if (!event.dataTransfer?.types?.includes('Files')) return;
        event.preventDefault();
        dragDepth += 1;
        dropIndicator.hidden = false;
    });

    document.addEventListener('dragover', (event) => {
        if (!event.dataTransfer?.types?.includes('Files')) return;
        event.preventDefault();
    });

    document.addEventListener('dragleave', (event) => {
        if (!event.dataTransfer?.types?.includes('Files')) return;
        dragDepth = Math.max(0, dragDepth - 1);
        if (dragDepth === 0) dropIndicator.hidden = true;
    });

    document.addEventListener('drop', (event) => {
        if (!event.dataTransfer?.files?.length) return;
        event.preventDefault();
        dragDepth = 0;
        dropIndicator.hidden = true;
        replaceQueuedFiles([...queuedFiles, ...Array.from(event.dataTransfer.files)]);
    });

    document.querySelectorAll('[data-close-preview]').forEach((button) => button.addEventListener('click', closeImagePreview));
    previewImage.addEventListener('load', () => {
        previewImage.hidden = false;
        previewError.hidden = true;
    });
    previewImage.addEventListener('error', () => {
        previewImage.hidden = true;
        previewError.hidden = false;
        setStatus('This image format cannot be previewed in this browser');
    });
    imagePreviewDialog.addEventListener('click', (event) => {
        if (event.target === imagePreviewDialog) closeImagePreview();
    });

    let initialView = 'details';
    try {
        initialView = window.localStorage.getItem('dropit-file-view') || 'details';
    } catch (_error) {
        initialView = 'details';
    }

    setView(initialView, false);
    applyFileView();
});
