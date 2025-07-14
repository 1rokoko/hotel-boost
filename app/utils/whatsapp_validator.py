"""
WhatsApp number validation utility for WhatsApp Hotel Bot application
"""

import re
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog

from app.core.logging import get_logger

logger = get_logger(__name__)


class ValidationStatus(Enum):
    """WhatsApp number validation status"""
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass
class WhatsAppValidationResult:
    """Result of WhatsApp number validation"""
    number: str
    formatted_number: str
    status: ValidationStatus
    is_whatsapp: Optional[bool] = None
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    carrier: Optional[str] = None
    line_type: Optional[str] = None
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    @property
    def is_valid(self) -> bool:
        """Check if number is valid"""
        return self.status == ValidationStatus.VALID
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "number": self.number,
            "formatted_number": self.formatted_number,
            "status": self.status.value,
            "is_whatsapp": self.is_whatsapp,
            "country_code": self.country_code,
            "country_name": self.country_name,
            "carrier": self.carrier,
            "line_type": self.line_type,
            "errors": self.errors,
            "warnings": self.warnings,
            "is_valid": self.is_valid
        }


class WhatsAppValidator:
    """Utility for validating WhatsApp numbers"""
    
    # Country code mappings for common countries
    COUNTRY_CODES = {
        "1": "US/CA",  # United States/Canada
        "7": "RU/KZ",  # Russia/Kazakhstan
        "20": "EG",    # Egypt
        "27": "ZA",    # South Africa
        "30": "GR",    # Greece
        "31": "NL",    # Netherlands
        "32": "BE",    # Belgium
        "33": "FR",    # France
        "34": "ES",    # Spain
        "36": "HU",    # Hungary
        "39": "IT",    # Italy
        "40": "RO",    # Romania
        "41": "CH",    # Switzerland
        "43": "AT",    # Austria
        "44": "GB",    # United Kingdom
        "45": "DK",    # Denmark
        "46": "SE",    # Sweden
        "47": "NO",    # Norway
        "48": "PL",    # Poland
        "49": "DE",    # Germany
        "51": "PE",    # Peru
        "52": "MX",    # Mexico
        "53": "CU",    # Cuba
        "54": "AR",    # Argentina
        "55": "BR",    # Brazil
        "56": "CL",    # Chile
        "57": "CO",    # Colombia
        "58": "VE",    # Venezuela
        "60": "MY",    # Malaysia
        "61": "AU",    # Australia
        "62": "ID",    # Indonesia
        "63": "PH",    # Philippines
        "64": "NZ",    # New Zealand
        "65": "SG",    # Singapore
        "66": "TH",    # Thailand
        "81": "JP",    # Japan
        "82": "KR",    # South Korea
        "84": "VN",    # Vietnam
        "86": "CN",    # China
        "90": "TR",    # Turkey
        "91": "IN",    # India
        "92": "PK",    # Pakistan
        "93": "AF",    # Afghanistan
        "94": "LK",    # Sri Lanka
        "95": "MM",    # Myanmar
        "98": "IR",    # Iran
        "212": "MA",   # Morocco
        "213": "DZ",   # Algeria
        "216": "TN",   # Tunisia
        "218": "LY",   # Libya
        "220": "GM",   # Gambia
        "221": "SN",   # Senegal
        "222": "MR",   # Mauritania
        "223": "ML",   # Mali
        "224": "GN",   # Guinea
        "225": "CI",   # Côte d'Ivoire
        "226": "BF",   # Burkina Faso
        "227": "NE",   # Niger
        "228": "TG",   # Togo
        "229": "BJ",   # Benin
        "230": "MU",   # Mauritius
        "231": "LR",   # Liberia
        "232": "SL",   # Sierra Leone
        "233": "GH",   # Ghana
        "234": "NG",   # Nigeria
        "235": "TD",   # Chad
        "236": "CF",   # Central African Republic
        "237": "CM",   # Cameroon
        "238": "CV",   # Cape Verde
        "239": "ST",   # São Tomé and Príncipe
        "240": "GQ",   # Equatorial Guinea
        "241": "GA",   # Gabon
        "242": "CG",   # Republic of the Congo
        "243": "CD",   # Democratic Republic of the Congo
        "244": "AO",   # Angola
        "245": "GW",   # Guinea-Bissau
        "246": "IO",   # British Indian Ocean Territory
        "248": "SC",   # Seychelles
        "249": "SD",   # Sudan
        "250": "RW",   # Rwanda
        "251": "ET",   # Ethiopia
        "252": "SO",   # Somalia
        "253": "DJ",   # Djibouti
        "254": "KE",   # Kenya
        "255": "TZ",   # Tanzania
        "256": "UG",   # Uganda
        "257": "BI",   # Burundi
        "258": "MZ",   # Mozambique
        "260": "ZM",   # Zambia
        "261": "MG",   # Madagascar
        "262": "RE",   # Réunion
        "263": "ZW",   # Zimbabwe
        "264": "NA",   # Namibia
        "265": "MW",   # Malawi
        "266": "LS",   # Lesotho
        "267": "BW",   # Botswana
        "268": "SZ",   # Eswatini
        "269": "KM",   # Comoros
        "290": "SH",   # Saint Helena
        "291": "ER",   # Eritrea
        "297": "AW",   # Aruba
        "298": "FO",   # Faroe Islands
        "299": "GL",   # Greenland
        "350": "GI",   # Gibraltar
        "351": "PT",   # Portugal
        "352": "LU",   # Luxembourg
        "353": "IE",   # Ireland
        "354": "IS",   # Iceland
        "355": "AL",   # Albania
        "356": "MT",   # Malta
        "357": "CY",   # Cyprus
        "358": "FI",   # Finland
        "359": "BG",   # Bulgaria
        "370": "LT",   # Lithuania
        "371": "LV",   # Latvia
        "372": "EE",   # Estonia
        "373": "MD",   # Moldova
        "374": "AM",   # Armenia
        "375": "BY",   # Belarus
        "376": "AD",   # Andorra
        "377": "MC",   # Monaco
        "378": "SM",   # San Marino
        "380": "UA",   # Ukraine
        "381": "RS",   # Serbia
        "382": "ME",   # Montenegro
        "383": "XK",   # Kosovo
        "385": "HR",   # Croatia
        "386": "SI",   # Slovenia
        "387": "BA",   # Bosnia and Herzegovina
        "389": "MK",   # North Macedonia
        "420": "CZ",   # Czech Republic
        "421": "SK",   # Slovakia
        "423": "LI",   # Liechtenstein
        "500": "FK",   # Falkland Islands
        "501": "BZ",   # Belize
        "502": "GT",   # Guatemala
        "503": "SV",   # El Salvador
        "504": "HN",   # Honduras
        "505": "NI",   # Nicaragua
        "506": "CR",   # Costa Rica
        "507": "PA",   # Panama
        "508": "PM",   # Saint Pierre and Miquelon
        "509": "HT",   # Haiti
        "590": "GP",   # Guadeloupe
        "591": "BO",   # Bolivia
        "592": "GY",   # Guyana
        "593": "EC",   # Ecuador
        "594": "GF",   # French Guiana
        "595": "PY",   # Paraguay
        "596": "MQ",   # Martinique
        "597": "SR",   # Suriname
        "598": "UY",   # Uruguay
        "599": "CW",   # Curaçao
        "670": "TL",   # East Timor
        "672": "NF",   # Norfolk Island
        "673": "BN",   # Brunei
        "674": "NR",   # Nauru
        "675": "PG",   # Papua New Guinea
        "676": "TO",   # Tonga
        "677": "SB",   # Solomon Islands
        "678": "VU",   # Vanuatu
        "679": "FJ",   # Fiji
        "680": "PW",   # Palau
        "681": "WF",   # Wallis and Futuna
        "682": "CK",   # Cook Islands
        "683": "NU",   # Niue
        "684": "AS",   # American Samoa
        "685": "WS",   # Samoa
        "686": "KI",   # Kiribati
        "687": "NC",   # New Caledonia
        "688": "TV",   # Tuvalu
        "689": "PF",   # French Polynesia
        "690": "TK",   # Tokelau
        "691": "FM",   # Federated States of Micronesia
        "692": "MH",   # Marshall Islands
        "850": "KP",   # North Korea
        "852": "HK",   # Hong Kong
        "853": "MO",   # Macau
        "855": "KH",   # Cambodia
        "856": "LA",   # Laos
        "880": "BD",   # Bangladesh
        "886": "TW",   # Taiwan
        "960": "MV",   # Maldives
        "961": "LB",   # Lebanon
        "962": "JO",   # Jordan
        "963": "SY",   # Syria
        "964": "IQ",   # Iraq
        "965": "KW",   # Kuwait
        "966": "SA",   # Saudi Arabia
        "967": "YE",   # Yemen
        "968": "OM",   # Oman
        "970": "PS",   # Palestine
        "971": "AE",   # United Arab Emirates
        "972": "IL",   # Israel
        "973": "BH",   # Bahrain
        "974": "QA",   # Qatar
        "975": "BT",   # Bhutan
        "976": "MN",   # Mongolia
        "977": "NP",   # Nepal
        "992": "TJ",   # Tajikistan
        "993": "TM",   # Turkmenistan
        "994": "AZ",   # Azerbaijan
        "995": "GE",   # Georgia
        "996": "KG",   # Kyrgyzstan
        "998": "UZ",   # Uzbekistan
    }
    
    def __init__(self):
        """Initialize WhatsApp validator"""
        self.logger = logger.bind(service="whatsapp_validator")
    
    def validate_format(self, number: str) -> WhatsAppValidationResult:
        """
        Validate WhatsApp number format
        
        Args:
            number: Phone number to validate
            
        Returns:
            WhatsAppValidationResult: Validation result
        """
        result = WhatsAppValidationResult(
            number=number,
            formatted_number="",
            status=ValidationStatus.INVALID
        )
        
        try:
            # Clean the number
            cleaned = self._clean_number(number)
            
            if not cleaned:
                result.errors.append("Number is empty or invalid")
                return result
            
            # Basic format validation
            if not self._validate_basic_format(cleaned):
                result.errors.append("Invalid phone number format")
                return result
            
            # Format the number
            formatted = self._format_number(cleaned)
            result.formatted_number = formatted
            
            # Extract country information
            country_code = self._extract_country_code(cleaned)
            if country_code:
                result.country_code = country_code
                result.country_name = self.COUNTRY_CODES.get(country_code, "Unknown")
            
            # Validate length constraints
            if not self._validate_length(cleaned):
                result.errors.append("Number length is invalid")
                return result
            
            # Check for common issues
            self._check_common_issues(cleaned, result)
            
            # If no errors, mark as valid
            if not result.errors:
                result.status = ValidationStatus.VALID
            
            self.logger.debug(
                "WhatsApp number format validated",
                number=number,
                formatted=result.formatted_number,
                status=result.status.value,
                country_code=result.country_code
            )
            
            return result
            
        except Exception as e:
            self.logger.error("WhatsApp number validation failed", number=number, error=str(e))
            result.status = ValidationStatus.ERROR
            result.errors.append(f"Validation error: {str(e)}")
            return result
    
    async def validate_whatsapp_availability(
        self,
        number: str,
        green_api_instance_id: Optional[str] = None,
        green_api_token: Optional[str] = None
    ) -> WhatsAppValidationResult:
        """
        Validate if number is available on WhatsApp (requires Green API)
        
        Args:
            number: Phone number to validate
            green_api_instance_id: Green API instance ID
            green_api_token: Green API token
            
        Returns:
            WhatsAppValidationResult: Validation result with WhatsApp availability
        """
        # First validate format
        result = self.validate_format(number)
        
        if not result.is_valid:
            return result
        
        # If Green API credentials are provided, check WhatsApp availability
        if green_api_instance_id and green_api_token:
            try:
                is_whatsapp = await self._check_whatsapp_availability(
                    result.formatted_number,
                    green_api_instance_id,
                    green_api_token
                )
                result.is_whatsapp = is_whatsapp
                
                if not is_whatsapp:
                    result.warnings.append("Number is not registered on WhatsApp")
                
            except Exception as e:
                self.logger.error(
                    "WhatsApp availability check failed",
                    number=number,
                    error=str(e)
                )
                result.warnings.append("Could not verify WhatsApp availability")
        
        return result
    
    def _clean_number(self, number: str) -> str:
        """Clean phone number by removing non-digit characters except +"""
        if not number:
            return ""
        
        # Remove all characters except digits and +
        cleaned = re.sub(r'[^\d+]', '', number.strip())
        
        # Ensure + is only at the beginning
        if '+' in cleaned:
            parts = cleaned.split('+')
            if len(parts) > 2 or (len(parts) == 2 and parts[0]):
                # Multiple + or + not at beginning
                cleaned = parts[-1]  # Take the last part
            else:
                cleaned = '+' + parts[1] if len(parts) == 2 else cleaned
        
        return cleaned
    
    def _validate_basic_format(self, number: str) -> bool:
        """Validate basic phone number format"""
        # Must start with + or digit, and contain only digits after +
        if number.startswith('+'):
            return bool(re.match(r'^\+[1-9]\d{1,14}$', number))
        else:
            return bool(re.match(r'^[1-9]\d{1,14}$', number))
    
    def _validate_length(self, number: str) -> bool:
        """Validate phone number length"""
        # Remove + for length calculation
        digits = number.lstrip('+')
        
        # International phone numbers should be 7-15 digits
        return 7 <= len(digits) <= 15
    
    def _format_number(self, number: str) -> str:
        """Format phone number with + prefix"""
        if number.startswith('+'):
            return number
        else:
            return '+' + number
    
    def _extract_country_code(self, number: str) -> Optional[str]:
        """Extract country code from phone number"""
        digits = number.lstrip('+')
        
        # Try to match country codes (1-4 digits)
        for length in range(1, 5):
            if len(digits) >= length:
                code = digits[:length]
                if code in self.COUNTRY_CODES:
                    return code
        
        return None
    
    def _check_common_issues(self, number: str, result: WhatsAppValidationResult):
        """Check for common issues and add warnings"""
        digits = number.lstrip('+')
        
        # Check for repeated digits
        if len(set(digits)) <= 2:
            result.warnings.append("Number contains mostly repeated digits")
        
        # Check for sequential digits
        if self._has_sequential_digits(digits):
            result.warnings.append("Number contains sequential digits")
        
        # Check for common test numbers
        test_patterns = ['1234567', '0000000', '1111111', '9999999']
        for pattern in test_patterns:
            if pattern in digits:
                result.warnings.append("Number appears to be a test number")
                break
    
    def _has_sequential_digits(self, digits: str) -> bool:
        """Check if number has sequential digits"""
        if len(digits) < 4:
            return False
        
        for i in range(len(digits) - 3):
            sequence = digits[i:i+4]
            if all(int(sequence[j]) == int(sequence[0]) + j for j in range(4)):
                return True
            if all(int(sequence[j]) == int(sequence[0]) - j for j in range(4)):
                return True
        
        return False
    
    async def _check_whatsapp_availability(
        self,
        number: str,
        instance_id: str,
        token: str
    ) -> bool:
        """
        Check if number is available on WhatsApp using Green API
        
        Args:
            number: Formatted phone number
            instance_id: Green API instance ID
            token: Green API token
            
        Returns:
            bool: True if number is on WhatsApp
        """
        try:
            # Format number for Green API (remove + and add @c.us)
            chat_id = number.lstrip('+') + '@c.us'
            
            url = f"https://api.green-api.com/waInstance{instance_id}/checkWhatsapp/{token}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"phoneNumber": chat_id},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("existsWhatsapp", False)
                    else:
                        self.logger.warning(
                            "Green API WhatsApp check failed",
                            status=response.status,
                            number=number
                        )
                        return False
                        
        except asyncio.TimeoutError:
            self.logger.warning("WhatsApp availability check timed out", number=number)
            return False
        except Exception as e:
            self.logger.error("WhatsApp availability check error", number=number, error=str(e))
            return False
    
    def batch_validate_format(self, numbers: List[str]) -> List[WhatsAppValidationResult]:
        """
        Validate multiple phone numbers
        
        Args:
            numbers: List of phone numbers to validate
            
        Returns:
            List[WhatsAppValidationResult]: List of validation results
        """
        results = []
        
        for number in numbers:
            result = self.validate_format(number)
            results.append(result)
        
        self.logger.info(
            "Batch validation completed",
            total_numbers=len(numbers),
            valid_numbers=sum(1 for r in results if r.is_valid),
            invalid_numbers=sum(1 for r in results if not r.is_valid)
        )
        
        return results


# Global validator instance
_validator_instance = None


def get_whatsapp_validator() -> WhatsAppValidator:
    """
    Get WhatsApp validator instance (singleton)
    
    Returns:
        WhatsAppValidator: Validator instance
    """
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = WhatsAppValidator()
    return _validator_instance


# Convenience functions
def validate_whatsapp_number(number: str) -> WhatsAppValidationResult:
    """
    Validate WhatsApp number format (convenience function)
    
    Args:
        number: Phone number to validate
        
    Returns:
        WhatsAppValidationResult: Validation result
    """
    validator = get_whatsapp_validator()
    return validator.validate_format(number)


async def check_whatsapp_availability(
    number: str,
    green_api_instance_id: str,
    green_api_token: str
) -> WhatsAppValidationResult:
    """
    Check WhatsApp availability (convenience function)
    
    Args:
        number: Phone number to check
        green_api_instance_id: Green API instance ID
        green_api_token: Green API token
        
    Returns:
        WhatsAppValidationResult: Validation result with availability
    """
    validator = get_whatsapp_validator()
    return await validator.validate_whatsapp_availability(
        number,
        green_api_instance_id,
        green_api_token
    )
