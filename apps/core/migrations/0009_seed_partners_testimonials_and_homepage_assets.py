from django.db import migrations
import os
import shutil
from PIL import Image

def seed_platform_assets(apps, schema_editor):
    from django.conf import settings
    PartnerOrganization = apps.get_model('core', 'PartnerOrganization')
    HomePageSetting = apps.get_model('core', 'HomePageSetting')
    Testimonial = apps.get_model('core', 'Testimonial')

    base_dir = str(settings.BASE_DIR)
    media_root = str(settings.MEDIA_ROOT)
    static_root = os.path.join(base_dir, 'static')

    partners_media_dir = os.path.join(media_root, 'partners')
    homepage_media_dir = os.path.join(media_root, 'homepage')
    os.makedirs(partners_media_dir, exist_ok=True)
    os.makedirs(homepage_media_dir, exist_ok=True)

    # 1. Partner Logos
    partner_strip_src = os.path.join(static_root, 'images/partner-logos.png')
    if os.path.exists(partner_strip_src):
        try:
            img = Image.open(partner_strip_src).convert('RGBA')
            w, h = img.size
            boxes = [
                ("who_logo.png", 0, 0, 115, h, "World Health Organization (WHO)", "https://www.who.int", 1),
                ("johns_hopkins_logo.png", 130, 0, 260, h, "Johns Hopkins Medicine", "https://www.hopkinsmedicine.org", 2),
                ("mayo_clinic_logo.png", 280, 0, 360, h, "Mayo Clinic", "https://www.mayoclinic.org", 3),
                ("nhs_logo.png", 385, 0, 470, h, "National Health Service (NHS)", "https://www.nhs.uk", 4),
                ("cleveland_clinic_logo.png", 495, 0, 620, h, "Cleveland Clinic", "https://my.clevelandclinic.org", 5),
                ("african_union_logo.png", 640, 0, 730, h, "African Union (AU)", "https://au.int", 6),
            ]
            for filename, x1, y1, x2, y2, name, url, order in boxes:
                sub = img.crop((x1, y1, x2, y2))
                bbox = sub.getbbox()
                if bbox:
                    sub = sub.crop(bbox)
                sub = sub.resize((sub.width * 2, sub.height * 2), Image.Resampling.LANCZOS)
                padded = Image.new('RGBA', (sub.width + 16, sub.height + 16), (0, 0, 0, 0))
                padded.paste(sub, (8, 8))
                out_path = os.path.join(partners_media_dir, filename)
                padded.save(out_path, format='PNG')

                # Create or update PartnerOrganization
                p, created = PartnerOrganization.objects.get_or_create(
                    name=name,
                    defaults={
                        'logo': f'partners/{filename}',
                        'website_url': url,
                        'display_order': order,
                        'is_active': True,
                    }
                )
                if not created and not p.logo:
                    p.logo = f'partners/{filename}'
                    p.save()
        except Exception as e:
            print(f"Error processing partner logos: {e}")

    # 2. Homepage Setting default images
    home_images = [
        ('images/hero_master_1024.png', 'hero_master_1024.png'),
        ('images/hero_founder_mobile_blended.png', 'hero_founder_mobile_blended.png'),
        ('images/ecosystem_doctor_hd.jpg', 'ecosystem_doctor_hd.jpg'),
        ('images/trust_security_hd.jpg', 'trust_security_hd.jpg'),
        ('images/partner-logos.png', 'partner-logos.png'),
    ]

    for src_rel, dest_filename in home_images:
        src = os.path.join(static_root, src_rel)
        dst = os.path.join(homepage_media_dir, dest_filename)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

    hp = HomePageSetting.objects.first()
    if not hp:
        hp = HomePageSetting.objects.create(title="Homepage Configuration")
    
    # Associate files if fields are blank
    if not hp.hero_background_image and os.path.exists(os.path.join(homepage_media_dir, 'hero_master_1024.png')):
        hp.hero_background_image = 'homepage/hero_master_1024.png'
    if not hp.hero_mobile_image and os.path.exists(os.path.join(homepage_media_dir, 'hero_founder_mobile_blended.png')):
        hp.hero_mobile_image = 'homepage/hero_founder_mobile_blended.png'
    if not hp.ecosystem_image and os.path.exists(os.path.join(homepage_media_dir, 'ecosystem_doctor_hd.jpg')):
        hp.ecosystem_image = 'homepage/ecosystem_doctor_hd.jpg'
    if not hp.trust_security_image and os.path.join(homepage_media_dir, 'trust_security_hd.jpg'):
        hp.trust_security_image = 'homepage/trust_security_hd.jpg'
    if not hp.partners_strip_image and os.path.exists(os.path.join(homepage_media_dir, 'partner-logos.png')):
        hp.partners_strip_image = 'homepage/partner-logos.png'
    hp.show_testimonials = True
    hp.save()

    # 3. Seed Initial Testimonials if none exist
    if Testimonial.objects.count() == 0:
        Testimonial.objects.create(
            author_name="Dr. Angela Mensah",
            role_title="VP of Clinical Operations & Quality",
            organization="St. Jude Specialist Hospital",
            rating=5,
            content="Kodafriq has transformed our revenue cycle operations. The verified clinical coders we hired achieved a 99.2% accuracy rate on complex ICD-10 inpatient charts, reducing our claim denials by 42% within 90 days. The verification process gives us complete hiring confidence.",
            display_order=1,
            is_active=True
        )
        Testimonial.objects.create(
            author_name="Emmanuel Okafor",
            role_title="Certified RHIA & Lead Clinical Coder",
            organization="Verified Kodafriq Healthcare Professional",
            rating=5,
            content="Passing the Kodafriq Clinical Competency Assessment gave my credentials instant international recognition. Within two weeks of receiving my verified badge, I was matched with a top healthcare network and secured a high-paying remote medical coding contract.",
            display_order=2,
            is_active=True
        )
        Testimonial.objects.create(
            author_name="Sarah Al-Mansoor",
            role_title="Director of Talent Acquisition",
            organization="Gulf Coast Medical Center",
            rating=5,
            content="The talent verification and pre-screened clinical evaluations on Kodafriq eliminated our staffing bottlenecks. Every candidate presented has proven competence in medical billing and CPT coding, saving our clinical teams hundreds of hours of interviewing.",
            display_order=3,
            is_active=True
        )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_testimonial_homepagesetting_show_testimonials_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_platform_assets, reverse_noop),
    ]
