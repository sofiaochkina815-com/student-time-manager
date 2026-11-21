from django.test import TestCase
from django.urls import reverse
from .knowledge import PUBLIC_PAGES


class PublicGuideTests(TestCase):
    def test_ten_distinct_substantive_pages_are_public_and_navigable(self):
        self.assertEqual(len(PUBLIC_PAGES), 10)
        self.assertEqual(len({page["title"] for page in PUBLIC_PAGES.values()}), 10)
        for slug, page in PUBLIC_PAGES.items():
            response = self.client.get(reverse("public_page", args=[slug]))
            self.assertContains(response, page["title"])
            self.assertGreater(sum(len(text) for title, text in page["sections"]), 400)
            self.assertContains(response, "Очкина София Леонидовна")
            for link in PUBLIC_PAGES:
                self.assertContains(response, reverse("public_page", args=[link]))

    def test_unknown_guide_is_a_real_404(self):
        self.assertEqual(self.client.get("/guide/unknown/").status_code, 404)
