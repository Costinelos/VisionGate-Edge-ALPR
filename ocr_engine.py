import pytesseract
import re
import logging

logger = logging.getLogger(__name__)


class OCREngine:
    def __init__(self):
        self.config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

        self.counties = [
            'AB', 'AR', 'AG', 'BC', 'BH', 'BN', 'BT', 'BR', 'BV', 'BZ',
            'CL', 'CS', 'CJ', 'CT', 'CV', 'DB', 'DJ', 'GL', 'GR', 'GJ',
            'HR', 'HD', 'IL', 'IS', 'IF', 'MM', 'MH', 'MS', 'NT', 'OT',
            'PH', 'SJ', 'SM', 'SB', 'SV', 'TR', 'TM', 'TL', 'VS', 'VL', 'VN', 'B'
        ]

    def recognize(self, image):
        if image is None: return None

        text = pytesseract.image_to_string(image, config=self.config).strip()
        clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())
        logger.info(f"[OCR RAW] '{clean_text}'")

        if len(clean_text) < 6: return None

        final_plate = self._smart_parse(clean_text)

        if final_plate:
            logger.info(f"[OCR FIX] '{clean_text}' -> '{final_plate}' (Format Valid)")
            return final_plate

        return None

    def _smart_parse(self, text):
        letter_map = str.maketrans("0185264", "OIBSZGA")

        for i in range(len(text) - 5):
            substring = text[i:]

            if len(substring) >= 2:
                possible_prefix = substring[:2].translate(letter_map)
                norm_substring = possible_prefix + substring[2:]
            else:
                continue

            if norm_substring.startswith('B') and len(norm_substring) >= 6:
                candidate = norm_substring[:7]
                if not self._check_bucuresti(candidate):
                    candidate = norm_substring[:6]
                    if not self._check_bucuresti(candidate):
                        continue

                return self._repair_plate(candidate, type='B')

            elif norm_substring[:2] in self.counties and len(norm_substring) >= 6:
                candidate = norm_substring[:8]
                if not self._check_judet(candidate):
                    candidate = norm_substring[:7]
                    if not self._check_judet(candidate):
                        continue

                return self._repair_plate(candidate, type='J')

        return None

    def _check_bucuresti(self, text):
        return len(text) in [6, 7] and text.startswith('B')

    def _check_judet(self, text):
        return len(text) in [7, 8] and text[:2] in self.counties

    def _repair_plate(self, text, type):
        if type == 'B':
            prefix = text[:1]
            rest = text[1:]
        else:
            prefix = text[:2]
            rest = text[2:]

        chars_part = rest[-3:]
        digits_part = rest[:-3]

        digits_fixed = digits_part.translate(str.maketrans("OIBZASG", "0182456"))
        chars_fixed = chars_part.translate(str.maketrans("0182456", "OIBZASG"))

        final = prefix + digits_fixed + chars_fixed

        if self._is_valid(final):
            return final
        return None

    def _is_valid(self, text):
        regex_buc = r'^B\d{2,3}[A-Z]{3}$'
        regex_jud = r'^[A-Z]{2}\d{2,3}[A-Z]{3}$'

        if text.startswith('B'):
            return re.match(regex_buc, text) is not None
        else:
            return re.match(regex_jud, text) is not None