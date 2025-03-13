import asyncio
import time
from urllib.parse import urlencode
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd

class Scraper:
    def __init__(self, url, keywords=None):
        self.url = url
        self.keywords = keywords
        self.data = []
        self.running = True
        self.max_retries = 3  # Number of retries for network errors

    async def start_scraping(self, update_callback):
        for attempt in range(self.max_retries):
            try:
                async with async_playwright() as p:
                    # **Use Chrome Instead of Firefox**
                    browser = await p.chromium.launch(headless=False)  # Change to True if needed
                    page = await browser.new_page()

                    # **Handle Noon.com Direct Search**
                    is_noon = "noon.com" in self.url
                    is_woocommerce = any(x in self.url for x in ["product", "shop", "store"])

                    if is_noon and self.keywords:
                        search_params = urlencode({"q": self.keywords})
                        self.url = f"{self.url.rstrip('/')}/search?{search_params}"

                    await page.goto(self.url, wait_until="networkidle")

                    # **Handle Search for WooCommerce & Other E-Commerce Sites**
                    if not is_noon and self.keywords:
                        search_selectors = [
                            'input.wp-block-search__input',  # Electra Store
                            'input[name="s"][type="search"]',  # General WooCommerce search
                            'input.dgwt-wcas-search-input'  # WooCommerce AJAX search
                        ]
                        search_box = None

                        for selector in search_selectors:
                            try:
                                await page.wait_for_selector(selector, state="visible", timeout=5000)
                                search_box = await page.query_selector(selector)
                                if search_box:
                                    break  # Found a valid search input
                            except PlaywrightTimeoutError:
                                continue  # Try next selector if this one fails

                        if search_box:
                            await search_box.focus()
                            await search_box.fill(self.keywords)
                            await search_box.press("Enter")
                            await page.wait_for_load_state("networkidle")

                    # **Dynamic Product Selectors**
                    product_selectors = {
                        "default": [
                            '.product-wrapper',  # Makerselectronics
                            'li.entry.has-media',  # Electra Store
                            '.product'  # Generic WooCommerce
                        ],
                        "noon": 'div.ProductBoxVertical_rocketBadgeBevel__lM0Ee'  # Noon.com product container
                    }

                    # **Pagination Selector**
                    next_page_selectors = {
                        "default": 'a.next.page-numbers',
                        "noon": 'a.PlpPagination_arrowLink__QSqKF[aria-disabled="false"]'  # Noon.com next page button
                    }

                    product_selector = product_selectors["noon"] if is_noon else product_selectors["default"]
                    next_page_selector = next_page_selectors["noon"] if is_noon else next_page_selectors["default"]

                    # **Scraping Loop**
                    while self.running:
                        # **Scroll Down to Load More Products for Noon**
                        if is_noon:
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            await asyncio.sleep(2)  # Allow time for products to load

                        # **Find Product Containers**
                        product_container = []
                        if isinstance(product_selector, list):
                            for selector in product_selector:
                                product_container = await page.query_selector_all(selector)
                                if product_container:
                                    break
                        else:
                            product_container = await page.query_selector_all(product_selector)

                        if not product_container:
                            print("⚠ No products found on this page.")
                            break

                        for product in product_container:
                            if not self.running:
                                break

                            # **Extract Product Name**
                            name_element = await product.query_selector('[data-qa="product-name"]') or \
                                           await product.query_selector('h3.heading-title.product-name a') or \
                                           await product.query_selector('h2 a') or \
                                           await product.query_selector('h3')
                            name = await name_element.inner_text() if name_element else "N/A"

                            # **Extract Price (Updated for Noon.com)**
                            price_element = await product.query_selector('strong.Price_amount__2sXa7') or \
                                            await product.query_selector('.price bdi') or \
                                            await product.query_selector('.woocommerce-Price-amount.amount')
                            price = await price_element.inner_text() if price_element else "N/A"

                            # **Extract Product Link (Updated for Noon.com)**
                            link_element = await product.query_selector('a')
                            link = await link_element.get_attribute("href") if link_element else "N/A"
                            if is_noon and link.startswith("/"):  # Convert relative links to full URLs
                                link = f"https://www.noon.com{link}"

                            # **Extract Product Image**
                            image_element = await product.query_selector('img')
                            image = await image_element.get_attribute("src") if image_element else "N/A"

                            # **Append Data and Update UI**
                            self.data.append({
                                "Name": name,
                                "Price": price,
                                "Link": link,
                                "Image": image
                            })
                            update_callback(self.data)

                        # **Pagination Handling for Noon**
                        next_page_button = await page.query_selector(next_page_selector)
                        if next_page_button:
                            print("🔄 Moving to the next page...")
                            await next_page_button.click()
                            await page.wait_for_load_state("networkidle")  # Wait for new products to load
                        else:
                            break  # Stop if no more pages

                    await browser.close()
                    break  # Successful run, exit retry loop

            except PlaywrightTimeoutError:
                print(f"⚠ Network error encountered (Attempt {attempt + 1}/{self.max_retries}) - Retrying...")
                time.sleep(3)  # Small delay before retrying

        print("✅ Scraping completed!")

    def stop(self):
        self.running = False

    def get_data(self):
        return pd.DataFrame(self.data)
