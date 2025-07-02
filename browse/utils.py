import subprocess
import tempfile
import json
import re

from pathlib import Path
from playwright.async_api import async_playwright

BASE_URL = "https://cds.climate.copernicus.eu"
DATASETS_URL = BASE_URL + "/datasets"
DATASET_URL_TEMPLATE = BASE_URL + "/datasets/{id}?tab=overview"

def ensure_playwright_installed():
    subprocess.run(["playwright", "install"], check=True)

async def scrape_datasets(progress=None, task=None, timeout=15000, scroll_step=700, scroll_timeout=750):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(DATASETS_URL)

        # Accept cookie/consent banner if present
        try:
            await page.click('button:has-text("Accept all cookies")', timeout=5000)
        except Exception:
            pass  # No consent banner

        # Wait for at least one article element to appear
        await page.wait_for_selector("article", timeout=15000)

        # Scroll using window.scrollBy and window.scrollY until the bottom
        last_position = await page.evaluate("window.scrollY")
        scroll_count = 0
        while True:
            await page.evaluate(f"window.scrollBy(0, {scroll_step})")
            await page.wait_for_timeout(scroll_timeout)
            current_position = await page.evaluate("window.scrollY")
            scroll_count += 1
            if progress and task is not None:
                progress.update(task, description=f"Scrolling page... (scroll {scroll_count})")
            if current_position == last_position:
                break
            last_position = current_position

        # Extract all dataset info
        if progress and task is not None:
            progress.update(task, description="Extracting dataset info...")
        articles = await page.query_selector_all("article")
        datasets = []
        for article in articles:
            # Dataset link (relative)
            link_el = await article.query_selector("a[href*='/datasets/']")
            rel_link = await link_el.get_attribute("href") if link_el else None

            id = re.sub(r"^.*?/datasets/(.*?)\?tab=overview", r"\1", rel_link) if rel_link else None

            # Title
            title_el = await article.query_selector("h3")
            title = await title_el.inner_text() if title_el else None

            # Description
            desc_el = await article.query_selector("p")
            description = await desc_el.inner_text() if desc_el else None

            # Tags (checkboxes/buttons)
            tag_els = await article.query_selector_all("button, [role='checkbox'], .cds-portal-tag, .cds-portal-chip, input[type='checkbox'] + label")
            tags = []
            for tag_el in tag_els:
                tag_text = await tag_el.inner_text()
                if tag_text:
                    tags.append(tag_text.strip())

            datasets.append({
                "id": id,
                "rel_link": rel_link,
                "abs_link": DATASET_URL_TEMPLATE.format(id=id) if id else None,
                "title": title,
                "description": description,
                "tags": tags,
            })
        await browser.close()
        return datasets

# Global variable to store the temp directory path
_temp_dir = None
_datasets_cache = None

def get_temp_dir():
    """Get or create temporary directory for storing datasets."""
    global _temp_dir
    if _temp_dir is None:
        _temp_dir = Path(tempfile.mkdtemp(prefix="cds_datasets_"))
    return _temp_dir

def write_datasets_to_temp(datasets_list):
    """Write datasets to temporary JSON file."""
    temp_dir = get_temp_dir()
    datasets_file = temp_dir / "datasets.json"
    
    with open(datasets_file, 'w', encoding='utf-8') as f:
        json.dump(datasets_list, f, indent=2, ensure_ascii=False)
    
    return datasets_file

def read_datasets_from_temp():
    """Read datasets from temporary JSON file."""
    global _datasets_cache
    if _datasets_cache is not None:
        return _datasets_cache
    
    temp_dir = get_temp_dir()
    datasets_file = temp_dir / "datasets.json"
    
    if datasets_file.exists():
        with open(datasets_file, 'r', encoding='utf-8') as f:
            _datasets_cache = json.load(f)
        return _datasets_cache
    return []