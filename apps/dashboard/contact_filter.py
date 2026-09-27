import re

class ContactInfoFilter:
    """
    Anti-circumvention filter that detects external contact information:
    - Phone numbers (international, Nigerian, dashed, spaced, parenthesized, digits spelled out)
    - Email addresses (standard RFC, obfuscated: [at], (at), at ... dot ...)
    - URLs & Websites (http, https, www, raw domains, shortened links)
    - Social / Messaging app handles (WhatsApp, Telegram, Skype, Zoom, LinkedIn, etc.)
    - Physical addresses (street, avenue, road, crescent, way, close, p.o. box, etc.)
    """

    # 1. Email pattern (standard and obfuscated)
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+(?:\s*@\s*|\s*\[at\]\s*|\s*\(at\)\s*|\s+at\s+)[A-Za-z0-9.-]+(?:\s*\.\s*|\s*\[dot\]\s*|\s*\(dot\)\s*|\s+dot\s+)[A-Za-z]{2,}\b',
        re.IGNORECASE
    )

    # 2. General URL / Domain pattern
    URL_PATTERN = re.compile(
        r'(?:https?://|ftp://|www\.)[^\s/$.?#].[^\s]*|'
        r'\b[a-zA-Z0-9][-a-zA-Z0-9]*\.(?:com|org|net|edu|gov|io|co|ng|uk|ca|me|xyz|app|site|online|tech|ai|dev|info|biz|link|tv|me)(?:/[^\s]*)?\b|'
        r'\b(?:wa\.me|t\.me|bit\.ly|tinyurl\.com|linktr\.ee)/[^\s]+\b',
        re.IGNORECASE
    )

    # 3. Social / Messaging platform handles & keywords
    SOCIAL_PLATFORM_PATTERN = re.compile(
        r'\b(?:whatsapp|whats\s*app|telegram|skype|zoom|wechat|signal|viber|linkedin|calendly)\b',
        re.IGNORECASE
    )

    # 4. Physical address patterns (e.g. 12 Marina Street, Plot 45 Admiralty Way, P.O. Box ...)
    ADDRESS_PATTERN = re.compile(
        r'\b(?:plot|no\.?|suite|flat|apartment|apt\.?|block|house)\s+\d+[^,\n]+(?:street|st|avenue|ave|road|rd|way|crescent|cres|close|cl|drive|dr|boulevard|blvd|lane|ln|estate|plaza|building)\b|'
        r'\b\d+\s+[a-zA-Z\s]{2,25}(?:street|st\.?|avenue|ave\.?|road|rd\.?|way|crescent|cres\.?|close|cl\.?|drive|dr\.?|boulevard|blvd\.?|lane|ln\.?|estate|plaza)\b|'
        r'\bp\.?o\.?\s*box\s+\d+\b',
        re.IGNORECASE
    )

    # Words representing digits (for spelled out numbers like "zero eight zero...")
    DIGIT_WORDS = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
    }

    POLICY_WARNING_MESSAGE = (
        "Message blocked: Sharing external contact details (phone numbers, email addresses, "
        "external links, social handles, or physical addresses) is strictly prohibited to "
        "protect candidate privacy, prevent circumvention, and ensure platform safety."
    )

    @classmethod
    def check_message(cls, text):
        """
        Scans text for contact information.
        Returns:
            is_flagged (bool): True if contact info detected.
            reasons (list): List of violation category names.
            snippets (list): Matched sensitive text segments.
        """
        if not text:
            return False, [], []

        reasons = []
        snippets = []

        # 1. Check for Emails
        email_matches = cls.EMAIL_PATTERN.findall(text)
        if email_matches:
            reasons.append("Email Address")
            snippets.extend(email_matches)

        # 2. Check for URLs / Links
        url_matches = cls.URL_PATTERN.findall(text)
        if url_matches:
            reasons.append("Website / External URL")
            snippets.extend(url_matches)

        # 3. Check for Social / Messaging Handles
        social_matches = cls.SOCIAL_PLATFORM_PATTERN.findall(text)
        if social_matches:
            reasons.append("External Messaging Handle (WhatsApp / Telegram / Skype / Zoom)")
            snippets.extend(social_matches)

        # 4. Check for Physical Addresses
        address_matches = cls.ADDRESS_PATTERN.findall(text)
        if address_matches:
            reasons.append("Physical Address")
            snippets.extend(address_matches)

        # 5. Check for Phone Numbers
        phone_matches = cls._extract_phone_numbers(text)
        if phone_matches:
            reasons.append("Phone Number")
            snippets.extend(phone_matches)

        is_flagged = len(reasons) > 0
        return is_flagged, sorted(list(set(reasons))), snippets

    @classmethod
    def _extract_phone_numbers(cls, text):
        found = []

        # Regex for phone numbers with punctuation/spaces (+234 803 123 4567, 0803-123-4567, (080) 1234567)
        phone_pattern = re.compile(
            r'(?:\+?\d{1,4}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b'
        )

        for match in phone_pattern.finditer(text):
            candidate = match.group(0).strip()
            digits_only = re.sub(r'\D', '', candidate)
            # If 7 or more digits and looks like a phone number (e.g. 7-15 digits)
            if 7 <= len(digits_only) <= 15:
                found.append(candidate)

        # Check for separated single digits (e.g. 0 8 0 3 1 2 3 4 5 6 7)
        spaced_digits = re.findall(r'(?:\b\d[\s-]{1,2}){6,}\d\b', text)
        if spaced_digits:
            found.extend(spaced_digits)

        # Check for word-spelled digits (e.g. "zero eight zero...")
        words = text.lower().split()
        spelled_count = 0
        spelled_seq = []
        for w in words:
            clean_w = re.sub(r'[^a-z]', '', w)
            if clean_w in cls.DIGIT_WORDS:
                spelled_count += 1
                spelled_seq.append(clean_w)
                if spelled_count >= 5:
                    found.append(" ".join(spelled_seq))
            else:
                spelled_count = 0
                spelled_seq = []

        return found
