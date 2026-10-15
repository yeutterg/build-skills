"""Crawl against a local site: sitemap index, JSON-LD product extraction, draft product files."""
import http.server
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGES = {
    "/sitemap.xml": '<?xml version="1.0"?><sitemapindex><sitemap><loc>{base}/sitemap_pages.xml</loc></sitemap></sitemapindex>',
    "/sitemap_pages.xml": '<?xml version="1.0"?><urlset><url><loc>{base}/</loc></url><url><loc>{base}/products/pour</loc></url><url><loc>{base}/pages/faq</loc></url></urlset>',
    "/": "<html><head><title>Acme</title><meta name='description' content='Kettles'></head><body><h1>Every cup, exactly right</h1></body></html>",
    "/products/pour": """<html><head><title>Pour</title><meta property='og:type' content='product'>
        <script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Acme Pour","sku":"AP1",
        "description":"Exact to the degree","offers":{"@type":"Offer","price":"129","priceCurrency":"USD"}}</script></head>
        <body><h1>Acme Pour</h1><h2>Exact to the degree</h2></body></html>""",
    "/pages/faq": "<html><head><title>FAQ</title></head><body><h1>Questions</h1></body></html>",
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        body = PAGES.get(path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body.replace("{base}", f"http://127.0.0.1:{self.server.server_port}").encode())

    def log_message(self, *args):
        pass


class CrawlTest(unittest.TestCase):
    def test_crawl_inventories_pages_and_products(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run([sys.executable, str(ROOT / "scripts" / "journey.py"), "crawl", tmp, "--url", base, "--date", "2026-10-15"], check=True, capture_output=True)
                res = json.loads((Path(tmp) / "discovery" / "crawl.json").read_text())
                kinds = {p["url"].replace(base, ""): p["kind"] for p in res["pages"]}
                self.assertEqual(kinds, {"/": "home", "/products/pour": "product", "/pages/faq": "support"})
                self.assertEqual([p["name"] for p in res["products"]], ["Acme Pour"])
                draft = (Path(tmp) / "products" / "pour.md").read_text()
                self.assertIn("review: draft", draft)
                self.assertIn("price: '129'", draft)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
