(function() {
    function initTinyMCE() {
        if (typeof tinymce === 'undefined') {
            setTimeout(initTinyMCE, 200);
            return;
        }

        tinymce.init({
            selector: 'textarea.rich-text-editor',
            height: 480,
            menubar: 'file edit view insert format tools table help',
            plugins: [
                'advlist', 'autolink', 'lists', 'link', 'image', 'charmap', 'preview',
                'anchor', 'searchreplace', 'visualblocks', 'code', 'fullscreen',
                'insertdatetime', 'media', 'table', 'help', 'wordcount'
            ],
            toolbar: 'undo redo | blocks fontfamily fontsize | bold italic underline strikethrough forecolor backcolor | ' +
                     'link image media | alignleft aligncenter alignright alignjustify | ' +
                     'bullist numlist outdent indent | table removeformat | code fullscreen preview',
            content_style: 'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: 15px; line-height: 1.7; color: #1e293b; padding: 14px; } ' +
                          'img { max-width: 100%; height: auto; border-radius: 8px; margin: 12px 0; } ' +
                          'table { border-collapse: collapse; width: 100%; margin: 16px 0; } ' +
                          'table td, table th { border: 1px solid #cbd5e1; padding: 8px 12px; } ' +
                          'pre, code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; font-family: monospace; } ' +
                          'video, iframe { max-width: 100%; border-radius: 8px; margin: 12px 0; }',
            media_live_embeds: true,
            paste_data_images: true,
            image_title: true,
            automatic_uploads: true,
            file_picker_types: 'image media file',
            branding: false,
            promotion: false,
            setup: function(editor) {
                editor.on('change keyup NodeChange', function() {
                    editor.save();
                });
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTinyMCE);
    } else {
        initTinyMCE();
    }
})();
