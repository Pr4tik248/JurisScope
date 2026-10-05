SUPPORTED_COUNTRIES = {"india": "India", "united states": "United States", "usa": "United States"}
INDIA_REGIONS = {"telangana", "andhra pradesh", "maharashtra", "delhi", "karnataka", "tamil nadu", "kerala", "uttar pradesh", "rajasthan", "west bengal"}

def resolve(country: str, state: str | None):
    canonical = SUPPORTED_COUNTRIES.get(country.strip().casefold())
    if not canonical: raise ValueError("Unsupported country. Choose India or United States.")
    region = (state or "").strip()
    if canonical == "India" and region and region.casefold() not in INDIA_REGIONS:
        raise ValueError("Unrecognized Indian state or region.")
    if canonical == "United States" and region and len(region) > 100:
        raise ValueError("Invalid state or region.")
    return canonical, region
