from django import forms

class RichTextEditorWidget(forms.Textarea):
    class Media:
        css = {
            'all': ('training/css/admin_tinymce.css',)
        }
        js = (
            'https://cdnjs.cloudflare.com/ajax/libs/tinymce/6.8.3/tinymce.min.js',
            'training/js/tinymce_init.js',
        )

    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'rich-text-editor',
            'rows': 16,
            'style': 'width: 100%; min-height: 380px;'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
