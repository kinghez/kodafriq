# Generated manually to clean legacy duplicate quiz content from QUIZ and MATCHING_QUIZ lessons

from django.db import migrations


def clean_quiz_duplicate_content(apps, schema_editor):
    ModuleLesson = apps.get_model('training', 'ModuleLesson')
    # For lessons configured as QUIZ or MATCHING_QUIZ that have lingering text in content:
    # clear content so the duplicate question text is removed from the database
    for lesson in ModuleLesson.objects.all():
        if lesson.lesson_type in ['QUIZ', 'MATCHING_QUIZ'] and lesson.content:
            lesson.content = ''
            lesson.save(update_fields=['content'])
        elif lesson.id == 7 and ('Knowledge Check' in (lesson.title or '') or 'Which of the following' in (lesson.content or '')):
            lesson.content = ''
            lesson.save(update_fields=['content'])


def reverse_clean_quiz_duplicate_content(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('training', '0010_modulelesson_quiz_questions_data'),
    ]

    operations = [
        migrations.RunPython(clean_quiz_duplicate_content, reverse_clean_quiz_duplicate_content),
    ]
