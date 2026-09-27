
# GOOGLE MAPS BUSINESS SCRAPER
# Google Colab / Jupyter - ONE CELL


import sys
import subprocess
import re
from urllib.parse import quote

# Install Python packages if needed


try:
    import pandas as pd
    from playwright.async_api import async_playwright
except ImportError:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q",
         "playwright", "pandas", "openpyxl"],
        check=True
    )

    import pandas as pd
    from playwright.async_api import async_playwright


# Helper functions

async def get_text(page, selector):
    try:
        element = page.locator(selector).first

        if await element.count():
            text = await element.inner_text()
            return text.strip()

    except Exception:
        pass

    return ""


async def get_attribute(page, selector, attribute):
    try:
        element = page.locator(selector).first

        if await element.count():
            value = await element.get_attribute(attribute)

            if value:
                return value.strip()

    except Exception:
        pass

    return ""


# ------------------------------------------------------------
# Google Maps scraper
# ------------------------------------------------------------

async def scrape_google_maps(keyword, location, max_results=20):

    search_query = quote(
        f"{keyword} in {location}"
    )

    maps_url = (
        "https://www.google.com/maps/search/"
        + search_query
    )

    results = []

    print("\nOpening Google Maps...")
    print("Search:", f"{keyword} in {location}")
    print()

    async with async_playwright() as p:

        # Launch Chromium
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )

        page = await browser.new_page(
            viewport={
                "width": 1440,
                "height": 900
            },
            locale="en-US"
        )

        # ----------------------------------------------------
        # Open Maps search
        # ----------------------------------------------------

        await page.goto(
            maps_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        await page.wait_for_timeout(5000)

        # ----------------------------------------------------
        # Find results panel
        # ----------------------------------------------------

        feed = page.locator(
            'div[role="feed"]'
        )

        if await feed.count() == 0:

            print(
                "ERROR: Google Maps results panel "
                "was not found."
            )

            await browser.close()

            return []

        # ----------------------------------------------------
        # Scroll results
        # ----------------------------------------------------

        links = []

        previous_count = 0

        for scroll_number in range(20):

            try:

                await feed.evaluate(
                    """
                    element => {
                        element.scrollTop =
                        element.scrollHeight;
                    }
                    """
                )

            except Exception:
                pass

            await page.wait_for_timeout(2000)

            try:

                current_links = await page.locator(
                    'a[href*="/maps/place/"]'
                ).evaluate_all(
                    """
                    elements =>
                    elements
                    .map(element => element.href)
                    .filter(Boolean)
                    """
                )

            except Exception:
                current_links = []

            # Remove duplicates
            links = list(
                dict.fromkeys(current_links)
            )

            print(
                f"Loading results... "
                f"{len(links)} found"
            )

            if len(links) >= max_results:
                break

            if len(links) == previous_count:

                await page.wait_for_timeout(3000)

            previous_count = len(links)

        # Limit results
        links = list(
            dict.fromkeys(links)
        )[:max_results]

        print()
        print(
            f"Found {len(links)} businesses."
        )
        print()
        print("Starting extraction...")
        print("-" * 70)

        # ----------------------------------------------------
        # Visit each business
        # ----------------------------------------------------

        for index, business_url in enumerate(
            links,
            start=1
        ):

            try:

                await page.goto(
                    business_url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                await page.wait_for_timeout(2500)

                # ------------------------------------------------
                # NAME
                # ------------------------------------------------

                name = await get_text(
                    page,
                    "h1"
                )

                # ------------------------------------------------
                # ADDRESS
                # ------------------------------------------------

                address = await get_attribute(
                    page,
                    'button[data-item-id="address"]',
                    "aria-label"
                )

                if address:

                    address = re.sub(
                        r"^Address:\s*",
                        "",
                        address,
                        flags=re.IGNORECASE
                    )

                # ------------------------------------------------
                # PHONE
                # ------------------------------------------------

                phone = await get_attribute(
                    page,
                    'button[data-item-id^="phone:"]',
                    "aria-label"
                )

                if phone:

                    phone = re.sub(
                        r"^Phone:\s*",
                        "",
                        phone,
                        flags=re.IGNORECASE
                    )

                # ------------------------------------------------
                # WEBSITE
                # ------------------------------------------------

                website = ""

                website_element = page.locator(
                    'a[data-item-id="authority"]'
                ).first

                if await website_element.count():

                    website = await website_element.get_attribute(
                        "href"
                    )

                # Fallback
                if not website:

                    website_element = page.locator(
                        'a[aria-label^="Website"]'
                    ).first

                    if await website_element.count():

                        website = await website_element.get_attribute(
                            "href"
                        )

                # ------------------------------------------------
                # RATING
                # ------------------------------------------------

                rating = ""

                rating_elements = page.locator(
                    '[role="img"][aria-label*="stars"]'
                )

                rating_count = await rating_elements.count()

                for i in range(rating_count):

                    try:

                        aria_label = (
                            await rating_elements
                            .nth(i)
                            .get_attribute("aria-label")
                        )

                        if not aria_label:
                            continue

                        match = re.search(
                            r"([\d.]+)",
                            aria_label
                        )

                        if match:

                            possible_rating = float(
                                match.group(1)
                            )

                            if (
                                0 <=
                                possible_rating <=
                                5
                            ):

                                rating = str(
                                    possible_rating
                                )

                                break

                    except Exception:
                        continue

                # ------------------------------------------------
                # Store result
                # ------------------------------------------------

                result = {
                    "Name": name,
                    "Phone": phone,
                    "Address": address,
                    "Website": website,
                    "Rating": rating
                }

                results.append(result)

                print(
                    f"{index}/{len(links)} | "
                    f"{name or 'Unknown'} | "
                    f"Rating: {rating or 'N/A'}"
                )

            except Exception as error:

                print(
                    f"{index}/{len(links)} | "
                    f"ERROR: {str(error)[:120]}"
                )

        # ----------------------------------------------------
        # Close browser
        # ----------------------------------------------------

        await browser.close()

    return results


# ============================================================
# USER INPUT
# ============================================================

print("=" * 70)
print("       GOOGLE MAPS BUSINESS SCRAPER")
print("=" * 70)

keyword = input(
    "\nEnter business keyword "
    "(example: restaurants): "
).strip()

location = input(
    "Enter location "
    "(example: Panipat, Haryana): "
).strip()

max_results_input = input(
    "Maximum number of results [20]: "
).strip()

if max_results_input:
    try:
        max_results = int(
            max_results_input
        )
    except ValueError:
        print(
            "Invalid number. Using 20."
        )
        max_results = 20
else:
    max_results = 20


# ============================================================
# VALIDATE INPUT
# ============================================================

if not keyword:

    raise ValueError(
        "Business keyword cannot be empty."
    )

if not location:

    raise ValueError(
        "Location cannot be empty."
    )

if max_results <= 0:

    raise ValueError(
        "Maximum results must be greater than 0."
    )


# ============================================================
# RUN SCRAPER
# ============================================================

data = await scrape_google_maps(
    keyword=keyword,
    location=location,
    max_results=max_results
)


# ============================================================
# SAVE TO EXCEL
# ============================================================

if data:

    df = pd.DataFrame(data)

    # Remove duplicate businesses
    df = df.drop_duplicates(
        subset=[
            "Name",
            "Address"
        ],
        keep="first"
    )

    # Reset row numbers
    df = df.reset_index(
        drop=True
    )

    filename = (
        "google_maps_businesses.xlsx"
    )

    df.to_excel(
        filename,
        index=False
    )

    print()
    print("=" * 70)
    print("SCRAPING COMPLETE")
    print("=" * 70)
    print(
        f"Businesses collected: {len(df)}"
    )
    print(
        f"Excel file: {filename}"
    )
    print("=" * 70)

    # Display results
    display(df)

    # --------------------------------------------------------
    # Automatically download in Google Colab
    # --------------------------------------------------------

    try:

        from google.colab import files

        print(
            "\nStarting Excel download..."
        )

        files.download(
            filename
        )

    except Exception:

        print(
            "\nIf the automatic download "
            "doesn't appear, the file is saved as:"
        )

        print(filename)

else:

    print()
    print("=" * 70)
    print("NO RESULTS FOUND")
    print("=" * 70)
    print(
        "Google Maps did not return any "
        "business results."
    )
