(function () {
    window.activeTinyEditor = null;

    /**
     * Calculates the viewport coordinate of the text cursor inside the editor iframe.
     */
    function getEditorCursorPosition(editor) {
        if (!editor || editor.destroyed) return null;
        try {
            var win = editor.getWin();
            var sel = win ? win.getSelection() : null;
            if (sel && sel.rangeCount > 0) {
                var range = sel.getRangeAt(0);
                var rects = range.getClientRects();
                var rect = rects.length > 0 ? rects[0] : range.getBoundingClientRect();
                var iframe = editor.getContentAreaContainer() ? editor.getContentAreaContainer().querySelector('iframe') : null;
                if (iframe && rect) {
                    var ifRect = iframe.getBoundingClientRect();
                    return {
                        x: ifRect.left + rect.left,
                        y: ifRect.top + rect.bottom + 4,
                        top: ifRect.top + rect.top,
                        height: rect.height || 18,
                        inViewport: (ifRect.top < window.innerHeight && ifRect.bottom > 0)
                    };
                }
            }
        } catch (e) { }
        return null;
    }

    /**
     * Positions a TinyMCE dropdown menu or popup precisely:
     * - Underneath clicked menubar/toolbar button, OR
     * - Next to the active sub-menu item, OR
     * - Directly next to the cursor when working in the textarea.
     */
    function positionMenuElement(menu) {
        if (!menu || !menu.classList) return;
        if (!menu.classList.contains('tox-menu') && !menu.classList.contains('tox-pop')) return;

        requestAnimationFrame(function () {
            var targetX = null;
            var targetY = null;
            var isButtonMenu = false;

            // 1. Check for active menubar button (e.g. File, Edit, Insert, Format, Tools, Table)
            var activeMbtn = document.querySelector('.tox-mbtn--active');
            if (activeMbtn) {
                var mRect = activeMbtn.getBoundingClientRect();
                targetX = mRect.left;
                targetY = mRect.bottom + 2;
                isButtonMenu = true;
            }

            // 2. Check for active toolbar button (e.g. dropdowns, font size, formats, align)
            if (targetX === null) {
                var activeTbtn = document.querySelector('.tox-tbtn--enabled, .tox-split-button--enabled');
                if (activeTbtn) {
                    var tRect = activeTbtn.getBoundingClientRect();
                    targetX = tRect.left;
                    targetY = tRect.bottom + 2;
                    isButtonMenu = true;
                }
            }

            // 3. Check for nested submenu item (e.g. Format -> Align -> Left)
            if (targetX === null) {
                var activeItem = document.querySelector('.tox-collection__item--active, .tox-collection__item[aria-expanded="true"]');
                if (activeItem) {
                    var iRect = activeItem.getBoundingClientRect();
                    targetX = iRect.right + 2;
                    targetY = iRect.top;
                }
            }

            // 4. If triggered while editing or right-clicking at cursor position
            if (targetX === null) {
                var ed = window.activeTinyEditor || (typeof tinymce !== 'undefined' ? tinymce.activeEditor : null);
                var cursor = getEditorCursorPosition(ed);
                if (cursor && cursor.inViewport) {
                    targetX = cursor.x;
                    targetY = cursor.y;
                }
            }

            // Fallback: If still null, check if current top is far below the screen
            if (targetX === null || targetY === null) {
                var ed = window.activeTinyEditor || (typeof tinymce !== 'undefined' ? tinymce.activeEditor : null);
                if (ed) {
                    var container = ed.getContainer();
                    if (container) {
                        var cRect = container.getBoundingClientRect();
                        targetX = cRect.left + 20;
                        targetY = cRect.top + 70;
                    }
                }
            }

            if (targetX !== null && targetY !== null) {
                var menuW = menu.offsetWidth || 230;
                var menuH = menu.offsetHeight || 280;
                var winW = window.innerWidth;
                var winH = window.innerHeight;

                // Screen boundary constraints
                if (targetX + menuW > winW - 12) {
                    targetX = Math.max(12, winW - menuW - 12);
                }

                // If button menu: only flip above if at the extreme bottom of the window (<120px space)
                if (isButtonMenu) {
                    if (targetY + 120 > winH && targetY - menuH > 40) {
                        targetY = Math.max(10, activeMbtn ? activeMbtn.getBoundingClientRect().top - menuH - 2 : targetY - menuH - 2);
                    }
                } else {
                    // For cursor/context menus, flip above cursor if not enough room below
                    if (targetY + menuH > winH - 12) {
                        targetY = Math.max(12, targetY - menuH - 24);
                    }
                }

                if (targetX < 12) targetX = 12;
                if (targetY < 12) targetY = 12;

                menu.style.setProperty('position', 'fixed', 'important');
                menu.style.setProperty('top', Math.round(targetY) + 'px', 'important');
                menu.style.setProperty('left', Math.round(targetX) + 'px', 'important');
                menu.style.setProperty('max-height', Math.round(Math.min(420, winH - targetY - 16)) + 'px', 'important');
                menu.style.setProperty('overflow-y', 'auto', 'important');
                menu.style.setProperty('z-index', '9999999', 'important');
            }
        });
    }

    // Global observer to catch dynamically spawned TinyMCE menus and popups
    function setupMenuObserver() {
        var observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                mutation.addedNodes.forEach(function (node) {
                    if (node.nodeType === 1) {
                        if (node.classList.contains('tox-menu') || node.classList.contains('tox-pop')) {
                            positionMenuElement(node);
                        } else {
                            var menus = node.querySelectorAll ? node.querySelectorAll('.tox-menu, .tox-pop') : [];
                            menus.forEach(positionMenuElement);
                        }
                    }
                });
            });
        });

        observer.observe(document.body, { childList: true, subtree: true });

        // Close or reposition menus on window scroll
        window.addEventListener('scroll', function () {
            var openMenus = document.querySelectorAll('.tox-menu');
            openMenus.forEach(function (menu) {
                positionMenuElement(menu);
            });
        }, { passive: true });
    }

    function getCsrfToken() {
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input && input.value) return input.value;
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, 10) === 'csrftoken=') {
                    cookieValue = decodeURIComponent(cookie.substring(10));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function initTinyMCE() {
        if (typeof tinymce === 'undefined') {
            setTimeout(initTinyMCE, 150);
            return;
        }

        setupMenuObserver();

        tinymce.init({
            selector: 'textarea.rich-text-editor',
            height: 540,
            skin: 'oxide-dark',
            content_css: 'dark',
            ui_mode: 'combined',
            toolbar_mode: 'wrap',
            menubar: 'file edit view insert format tools table help',
            plugins: [
                'advlist', 'autolink', 'lists', 'link', 'image', 'charmap', 'preview',
                'anchor', 'searchreplace', 'visualblocks', 'code', 'fullscreen',
                'insertdatetime', 'media', 'table', 'help', 'wordcount', 'quickbars'
            ],
            quickbars_selection_toolbar: 'bold italic underline | blocks | forecolor backcolor | link table',
            quickbars_insert_toolbar: 'quicktable quickimage | bullist numlist',
            contextmenu: 'link image table configurecell cell row column',
            toolbar: [
                'undo redo | blocks fontfamily fontsize | bold italic underline strikethrough forecolor backcolor',
                'alignleft aligncenter alignright alignjustify | uploadimage uploadvideo insertdocument | image media table link | bullist numlist outdent indent | code fullscreen preview'
            ],
            image_advtab: true,
            image_caption: true,
            image_dimensions: true,
            image_class_list: [
                { title: 'Default (Responsive)', value: 'kf-img-responsive' },
                { title: 'Float Left (Text Wraps Right)', value: 'kf-img-left' },
                { title: 'Float Right (Text Wraps Left)', value: 'kf-img-right' },
                { title: 'Centered Block', value: 'kf-img-center' },
                { title: 'Full Width Hero', value: 'kf-img-full' },
                { title: 'Clinical Scan / Bordered Card', value: 'kf-img-card' }
            ],
            content_style: 'body { background-color: #0b1739 !important; color: #ffffff !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: 15px; line-height: 1.7; padding: 18px; } ' +
                'p, span, div, li, td, th { color: #ffffff !important; } ' +
                'h1, h2, h3, h4, h5, h6 { color: #38bdf8 !important; font-weight: 700; } ' +
                'a { color: #38bdf8 !important; text-decoration: underline; } ' +
                'img { max-width: 100%; height: auto; border-radius: 8px; margin: 12px 0; } ' +
                'img.kf-img-left, figure.kf-img-left { float: left !important; margin: 4px 28px 20px 0 !important; max-width: 48% !important; } ' +
                'img.kf-img-right, figure.kf-img-right { float: right !important; margin: 4px 0 20px 28px !important; max-width: 48% !important; } ' +
                'img.kf-img-center, figure.kf-img-center { display: block !important; margin: 20px auto !important; max-width: 85% !important; } ' +
                'img.kf-img-full, figure.kf-img-full { width: 100% !important; max-width: 100% !important; height: auto !important; display: block !important; margin: 20px 0 !important; } ' +
                'img.kf-img-card, figure.kf-img-card { border: 1px solid #334155 !important; padding: 8px !important; background: #0f172a !important; border-radius: 10px !important; } ' +
                'figure.image { display: inline-block; margin: 16px 0; } ' +
                'figure.image figcaption { font-size: 0.85rem; color: #94a3b8; margin-top: 6px; text-align: center; font-style: italic; } ' +
                'table { border-collapse: collapse; width: 100%; margin: 16px 0; color: #ffffff; } ' +
                'table td, table th { border: 1px solid #334155; padding: 10px 14px; color: #ffffff; } ' +
                'pre, code { background: #1e293b; color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; font-family: monospace; } ' +
                'video, iframe { max-width: 100%; border-radius: 8px; margin: 12px 0; }',
            media_live_embeds: true,
            paste_data_images: true,
            image_title: true,
            automatic_uploads: true,
            images_upload_url: '/training/admin/upload-media/',
            images_upload_handler: function (blobInfo, progress) {
                return new Promise(function (resolve, reject) {
                    var xhr = new XMLHttpRequest();
                    xhr.withCredentials = true;
                    xhr.open('POST', '/training/admin/upload-media/');
                    var token = getCsrfToken();
                    if (token) {
                        xhr.setRequestHeader('X-CSRFToken', token);
                    }
                    xhr.upload.onprogress = function (e) {
                        progress(e.loaded / e.total * 100);
                    };
                    xhr.onload = function () {
                        if (xhr.status < 200 || xhr.status >= 300) {
                            reject('Upload failed (HTTP ' + xhr.status + '): ' + xhr.responseText);
                            return;
                        }
                        try {
                            var json = JSON.parse(xhr.responseText);
                            if (!json || typeof json.location !== 'string') {
                                reject('Invalid server response: ' + xhr.responseText);
                                return;
                            }
                            resolve(json.location);
                        } catch (err) {
                            reject('JSON Parse Error: ' + err.message);
                        }
                    };
                    xhr.onerror = function () {
                        reject('Network error encountered during media upload.');
                    };
                    var formData = new FormData();
                    formData.append('file', blobInfo.blob(), blobInfo.filename());
                    xhr.send(formData);
                });
            },
            file_picker_types: 'image media file',
            file_picker_callback: function (cb, value, meta) {
                var input = document.createElement('input');
                input.setAttribute('type', 'file');
                if (meta.filetype === 'image') {
                    input.setAttribute('accept', 'image/*');
                } else if (meta.filetype === 'media') {
                    input.setAttribute('accept', 'video/*,audio/*');
                } else {
                    input.setAttribute('accept', '*/*');
                }
                input.onchange = function () {
                    var file = this.files[0];
                    if (!file) return;

                    var formData = new FormData();
                    formData.append('file', file);
                    var xhr = new XMLHttpRequest();
                    xhr.withCredentials = true;
                    xhr.open('POST', '/training/admin/upload-media/');
                    var token = getCsrfToken();
                    if (token) {
                        xhr.setRequestHeader('X-CSRFToken', token);
                    }
                    xhr.onload = function () {
                        if (xhr.status >= 200 && xhr.status < 300) {
                            try {
                                var json = JSON.parse(xhr.responseText);
                                if (json && json.location) {
                                    cb(json.location, { title: file.name, text: file.name, alt: file.name });
                                } else {
                                    alert('Media upload failed: Invalid response format');
                                }
                            } catch (e) {
                                alert('Error parsing server response: ' + e.message);
                            }
                        } else {
                            alert('Media upload failed (' + xhr.status + '): ' + xhr.responseText);
                        }
                    };
                    xhr.onerror = function () {
                        alert('Network connection failure while uploading media.');
                    };
                    xhr.send(formData);
                };
                input.click();
            },
            branding: false,
            promotion: false,
            setup: function (editor) {
                // Direct "Upload Image from Computer" Toolbar Button
                editor.ui.registry.addButton('uploadimage', {
                    icon: 'image',
                    tooltip: 'Upload Image from Computer (Instant)',
                    onAction: function () {
                        uploadMediaDirectly(editor, 'image/*');
                    }
                });

                // Direct "Upload Video from Computer" Toolbar Button
                editor.ui.registry.addButton('uploadvideo', {
                    icon: 'embed',
                    tooltip: 'Upload Video from Computer (MP4, WebM)',
                    onAction: function () {
                        uploadMediaDirectly(editor, 'video/*');
                    }
                });

                // Direct "Upload Document/PDF from Computer" Toolbar Button
                editor.ui.registry.addButton('insertdocument', {
                    icon: 'browse',
                    tooltip: 'Upload Document / PDF from Computer',
                    onAction: function () {
                        uploadMediaDirectly(editor, '.pdf,.doc,.docx,.xlsx,.pptx');
                    }
                });

                // Helper to trigger OS file chooser, upload via AJAX, and insert element
                function uploadMediaDirectly(ed, acceptTypes) {
                    var input = document.createElement('input');
                    input.setAttribute('type', 'file');
                    input.setAttribute('accept', acceptTypes);
                    input.onchange = function () {
                        var file = this.files[0];
                        if (!file) return;

                        var notif = null;
                        if (ed.notificationManager) {
                            notif = ed.notificationManager.open({
                                text: 'Uploading ' + file.name + ' (' + (file.size / (1024 * 1024)).toFixed(1) + 'MB)... Please wait.',
                                type: 'info',
                                timeout: false
                            });
                        }

                        var formData = new FormData();
                        formData.append('file', file);

                        var xhr = new XMLHttpRequest();
                        xhr.withCredentials = true;
                        xhr.open('POST', '/training/admin/upload-media/');
                        var token = getCsrfToken();
                        if (token) {
                            xhr.setRequestHeader('X-CSRFToken', token);
                        }

                        xhr.onload = function () {
                            if (notif) notif.close();
                            if (xhr.status >= 200 && xhr.status < 300) {
                                try {
                                    var json = JSON.parse(xhr.responseText);
                                    if (json && json.location) {
                                        var isVideo = file.type.startsWith('video/') || /\.(mp4|webm|mov|mkv|avi)$/i.test(file.name);
                                        var isImage = file.type.startsWith('image/') || /\.(jpg|jpeg|png|gif|webp|svg)$/i.test(file.name);

                                        if (isImage) {
                                            ed.insertContent('<p><img src="' + json.location + '" alt="' + file.name + '" class="kf-img-responsive" style="max-width: 100%; height: auto; border-radius: 8px; margin: 14px 0;" /></p>');
                                        } else if (isVideo) {
                                            ed.insertContent('<div style="margin: 20px 0; border-radius: 8px; overflow: hidden; background: #000000;"><video controls style="width: 100%; max-height: 480px; display: block;" preload="metadata"><source src="' + json.location + '" type="video/mp4">Your browser does not support HTML5 video.</video></div><p>&nbsp;</p>');
                                        } else {
                                            ed.insertContent('<p><a href="' + json.location + '" target="_blank" style="display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; background: #1e293b; color: #38bdf8; border-radius: 6px; text-decoration: none; font-weight: 700; font-size: 0.9rem;">📄 Download ' + file.name + ' &nearr;</a></p><p>&nbsp;</p>');
                                        }

                                        if (ed.notificationManager) {
                                            ed.notificationManager.open({
                                                text: '✓ ' + file.name + ' uploaded and inserted successfully!',
                                                type: 'success',
                                                timeout: 4000
                                            });
                                        }
                                    } else {
                                        alert('Upload error: Invalid response from server');
                                    }
                                } catch (e) {
                                    alert('Error processing server response: ' + e.message);
                                }
                            } else {
                                alert('Upload failed (' + xhr.status + '): ' + xhr.responseText);
                            }
                        };

                        xhr.onerror = function () {
                            if (notif) notif.close();
                            alert('Network error while uploading ' + file.name);
                        };

                        xhr.send(formData);
                    };
                    input.click();
                }

                editor.on('focus', function () {
                    window.activeTinyEditor = editor;
                });
                editor.on('click keyup NodeChange selectionchange', function () {
                    window.activeTinyEditor = editor;
                    editor.save();
                });
                editor.on('OpenMenu', function (e) {
                    window.activeTinyEditor = editor;
                    setTimeout(function () {
                        var openMenus = document.querySelectorAll('.tox-menu');
                        openMenus.forEach(positionMenuElement);
                    }, 10);
                });
            }
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTinyMCE);
    } else {
        initTinyMCE();
    }
})();
