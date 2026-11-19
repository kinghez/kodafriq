from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe


class RichTextEditorWidget(forms.Textarea):
    class Media:
        css = {
            'all': ('training/css/admin_tinymce.css?v=3',)
        }
        js = (
            'https://cdnjs.cloudflare.com/ajax/libs/tinymce/6.8.3/tinymce.min.js',
            'training/js/tinymce_uploader_v3.js',
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

    def render(self, name, value, attrs=None, renderer=None):
        textarea_html = super().render(name, value, attrs, renderer)
        elem_id = (attrs or {}).get('id', f'id_{name}')
        toolbar_html = format_html(
            '<div style="margin: 10px 0 8px 0; padding: 10px 14px; background: #0e1b3d; border: 1px solid #1e293b; border-radius: 8px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">'
            '<span style="font-size: 12px; font-weight: 800; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px;">Media Uploader:</span>'
            '<button type="button" onclick="window.kfDirectUpload(\'{}\', \'image\')" style="display: inline-flex; align-items: center; gap: 6px; background: #0284c7; color: #ffffff; border: none; padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 13px; cursor: pointer; box-shadow: 0 2px 6px rgba(2,132,199,0.3);">'
            '📷 Upload Image from Computer</button>'
            '<button type="button" onclick="window.kfDirectUpload(\'{}\', \'video\')" style="display: inline-flex; align-items: center; gap: 6px; background: #6366f1; color: #ffffff; border: none; padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 13px; cursor: pointer; box-shadow: 0 2px 6px rgba(99,102,241,0.3);">'
            '🎬 Upload Video from Computer (MP4)</button>'
            '<span style="font-size: 12px; color: #94a3b8;">(Select file directly from your PC to insert into the editor)</span>'
            '</div>',
            elem_id,
            elem_id
        )
        return mark_safe(toolbar_html + textarea_html)
