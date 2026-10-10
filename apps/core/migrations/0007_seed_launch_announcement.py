import os
import shutil
from django.conf import settings
from django.db import migrations


def seed_launch_announcement(apps, schema_editor):
    Announcement = apps.get_model('core', 'Announcement')

    try:
        static_launch_dir = os.path.join(settings.BASE_DIR, 'static', 'images', 'launch')
        media_ann_dir = os.path.join(settings.MEDIA_ROOT, 'announcements')
        os.makedirs(media_ann_dir, exist_ok=True)
        for fname in ['launch_agenda.jpg', 'keynote_speakers.jpg']:
            src = os.path.join(static_launch_dir, fname)
            dst = os.path.join(media_ann_dir, fname)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
    except Exception:
        pass

    if not Announcement.objects.filter(title="Official Launch of Kodafriq Digital Platform").exists():
        Announcement.objects.create(
            title="Official Launch of Kodafriq Digital Platform",
            eyebrow_badge="🎉 LIVE TODAY • OFFICIAL PLATFORM LAUNCH",
            headline="Global Healthcare Talent Without Borders — Connecting Skilled Professionals with Global Opportunities",
            body_text=(
                "Kodafriq Data Management Solutions is officially launching today! "
                "Join our distinguished leadership, clinical specialists, and keynote speakers for the live unveiling of Africa's premier verified healthcare talent marketplace.\n\n"
                "Keynote Speakers:\n"
                "• Mrs Eugenia S — Managing Director & Founder\n"
                "• Kennedy N — Medical Coding & Billing Specialist\n"
                "• Elochukwu E — Quality Control Manager\n"
                "• Henry C — Medical Coding & Billing Specialist\n"
                "• Hezekiah — Lead Programmer, Kodafriq Platform\n\n"
                "Launch Agenda Highlights:\n"
                "1. Welcome & Opening Remarks (Vision & Purpose)\n"
                "2. Kodafriq Candidate Success Story (RedHouse Opportunity)\n"
                "3. Candidate Verification Process & Score Rigor\n"
                "4. Medical Billing Training Programme\n"
                "5. Kodafriq Platform Video Demonstration\n"
                "6. Live Questions & Answers Session\n"
                "7. Official Platform Launch & Closing Remarks"
            ),
            event_datetime_text="Saturday, 10 October 2026 • 5:00 PM UK / 4:00 PM GHANA",
            event_location_text="Online Live via Google Meet",
            image="announcements/launch_agenda.jpg",
            secondary_image="announcements/keynote_speakers.jpg",
            image_alt_text="Kodafriq Official Platform Launch Agenda & Keynote Speakers",
            primary_action_text="Join Launch Live Online",
            primary_action_url="https://calendar.app.google/ox5GwEg89EsPeYJ39",
            primary_action_new_tab=True,
            secondary_action_text="Register as Candidate",
            secondary_action_url="/accounts/register/candidate/",
            target_placement="both",
            display_mode="both",
            content_format="full",
            popup_trigger_type="delay",
            popup_delay_seconds=3,
            random_min_interval_seconds=25,
            random_max_interval_seconds=75,
            allow_dismiss=True,
            remember_dismissal_hours=0,
            is_active=True,
            priority=100,
        )


def remove_launch_announcement(apps, schema_editor):
    Announcement = apps.get_model('core', 'Announcement')
    Announcement.objects.filter(title="Official Launch of Kodafriq Digital Platform").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_announcement'),
    ]

    operations = [
        migrations.RunPython(seed_launch_announcement, remove_launch_announcement),
    ]
