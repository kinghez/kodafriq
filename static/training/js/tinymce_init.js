(function() {
    function initTinyMCE() {
        if (typeof tinymce === 'undefined') {
            setTimeout(initTinyMCE, 150);
            return;
        }

        tinymce.init({
            selector: 'textarea.rich-text-editor',
            height: 520,
            skin: 'oxide-dark',
            content_css: 'dark',
            ui_mode: 'combined',
            menubar: 'file edit view insert format tools table help',
            plugins: [
                'advlist', 'autolink', 'lists', 'link', 'image', 'charmap', 'preview',
                'anchor', 'searchreplace', 'visualblocks', 'code', 'fullscreen',
                'insertdatetime', 'media', 'table', 'help', 'wordcount'
            ],
            toolbar: 'undo redo | blocks fontfamily fontsize | bold italic underline strikethrough forecolor backcolor | ' +
                     'link image media | alignleft aligncenter alignright alignjustify | ' +
                     'bullist numlist outdent indent | table removeformat | code fullscreen preview',
            content_style: 'body { background-color: #0b1739 !important; color: #ffffff !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: 15px; line-height: 1.7; padding: 18px; } ' +
                          'p, span, div, li, td, th { color: #ffffff !important; } ' +
                          'h1, h2, h3, h4, h5, h6 { color: #38bdf8 !important; font-weight: 700; } ' +
                          'a { color: #38bdf8 !important; text-decoration: underline; } ' +
                          'img { max-width: 100%; height: auto; border-radius: 8px; margin: 12px 0; } ' +
                          'table { border-collapse: collapse; width: 100%; margin: 16px 0; color: #ffffff; } ' +
                          'table td, table th { border: 1px solid #334155; padding: 10px 14px; color: #ffffff; } ' +
                          'pre, code { background: #1e293b; color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; font-family: monospace; } ' +
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
