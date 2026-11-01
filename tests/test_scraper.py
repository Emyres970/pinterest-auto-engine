import unittest
from unittest.mock import Mock, patch

from modules import scraper


def make_article_html():
    paragraphs = [
        (
            "A person may begin to question their own judgment when "
            "someone repeatedly changes the meaning of ordinary events. "
            "This can make everyday conversations feel confusing."
        ),
        (
            "One common pattern is that the other person denies statements "
            "they previously made, even when the conversation was clear. "
            "The disagreement gradually becomes about your memory."
        ),
        (
            "Another pattern appears when reasonable questions are treated "
            "as personal attacks. Instead of discussing the original issue, "
            "the conversation shifts toward your supposed attitude."
        ),
        (
            "Over time, these repeated interactions can make someone "
            "hesitate before raising ordinary concerns. They may spend more "
            "time defending their memory than discussing the problem."
        ),
    ]

    body = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)

    return f"""
    <html>
      <head>
        <title>Understanding Repeated Relationship Patterns</title>
        <meta property="og:title"
              content="Understanding Repeated Relationship Patterns">
      </head>
      <body>
        <nav>
          <p>Home Relationships Contact About</p>
        </nav>

        <article>
          <h1>Understanding Repeated Relationship Patterns</h1>

          <div class="sidebar">
            <p>This is unrelated sidebar content and should not be extracted.</p>
          </div>

          <div class="post-body">
            {body}

            <div class="post-footer">
              <p>Share this post with your friends.</p>
            </div>
          </div>

          <div class="comments">
            <p>This is a comment and should not be extracted.</p>
          </div>
        </article>

        <footer>
          <p>Copyright. Privacy policy. Terms and conditions.</p>
        </footer>
      </body>
    </html>
    """


class BloggerScraperTests(unittest.TestCase):

    def test_extracts_blogger_post_body(self):
        result = scraper._parse_html(make_article_html())

        self.assertEqual(
            result["title"],
            "Understanding Repeated Relationship Patterns",
        )

        self.assertGreater(len(result["body"]), 300)
        self.assertIn("repeatedly changes the meaning", result["body"])
        self.assertIn("reasonable questions", result["body"])

    def test_excludes_sidebar_comments_and_page_chrome(self):
        result = scraper._parse_html(make_article_html())
        body = result["body"].casefold()

        self.assertNotIn("unrelated sidebar content", body)
        self.assertNotIn("this is a comment", body)
        self.assertNotIn("privacy policy", body)
        self.assertNotIn("share this post", body)

    def test_does_not_use_generic_body_as_article(self):
        html = """
        <html>
          <head><title>A Page Without Article Markup</title></head>
          <body>
            <nav><p>Navigation text that is not an article.</p></nav>
            <div class="sidebar">
              <p>Sidebar content that should not become article text.</p>
            </div>
          </body>
        </html>
        """

        result = scraper._parse_html(html)

        self.assertEqual(result["title"], "A Page Without Article Markup")
        self.assertEqual(result["body"], "")

    def test_http_path_returns_usable_article(self):
        response = Mock()
        response.text = make_article_html()
        response.raise_for_status.return_value = None

        with patch.object(scraper.requests, "get", return_value=response):
            result = scraper._scrape_with_requests(
                "https://example.blogspot.com/article.html"
            )

        self.assertIsNotNone(result)
        self.assertGreater(len(result["body"]), 300)

    def test_http_path_rejects_incomplete_article(self):
        response = Mock()
        response.text = """
        <html>
          <head><title>Short Page</title></head>
          <body>
            <div class="post-body">
              <p>This is only a very short extracted paragraph.</p>
            </div>
          </body>
        </html>
        """
        response.raise_for_status.return_value = None

        with patch.object(scraper.requests, "get", return_value=response):
            result = scraper._scrape_with_requests(
                "https://example.blogspot.com/short.html"
            )

        self.assertIsNone(result)

    def test_old_function_name_remains_compatible(self):
        expected = {
            "title": "A Blogger article",
            "body": "Article body text",
        }

        with patch.object(
            scraper,
            "scrape_article",
            return_value=expected,
        ) as mocked:
            result = scraper.scrape_medium_post(
                "https://example.blogspot.com/article.html"
            )

        self.assertEqual(result, expected)
        mocked.assert_called_once_with(
            "https://example.blogspot.com/article.html"
        )

    def test_empty_url_is_rejected(self):
        with self.assertRaises(ValueError):
            scraper.scrape_article("")


if __name__ == "__main__":
    unittest.main()
