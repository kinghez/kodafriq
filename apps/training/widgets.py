from django import forms


class RichTextEditorWidget(forms.Textarea):
    class Media:
        css = {
            'all': ('training/css/admin_tinymce.css?v=4',)
        }
        js = (
            'https://cdnjs.cloudflare.com/ajax/libs/tinymce/6.8.3/tinymce.min.js',
            'training/js/enterprise_editor_v4.js',
        )

    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'rich-text-editor',
            'rows': 18,
            'style': 'width: 100%; min-height: 420px;'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
