import unittest
from unittest.mock import Mock, patch

from modules import scraper


def _long_paragraph(topic):
    return (
        f"{topic} can affect the way people understand difficult relationship "
        "experiences. A person may begin to question ordinary conversations "
        "when the same disagreement repeatedly changes direction. Instead of "
        "discussing the original event, the conversation can become focused "
        "on the person's memory, intentions, or emotional reaction. Over time, "
        "this pattern can make it harder to raise reasonable concerns and "
        "can cause someone to spend more energy defending their recollection "
        "than resolving the issue. Recognising the repeated pattern helps "
        "the reader understand why the interaction feels confusing."
    )


def make_article_html():
    paragraphs = [
        _long_paragraph("Repeated denial"),
        _long_paragraph("Blame shifting"),
        _long_paragraph("Changing the subject"),
        _long_paragraph("The gradual loss of confidence"),
    ]

    body = "".join(f"<p>{p}</p>" for p in paragraphs)

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


def make_feed_xml(article_url):
    paragraphs = [
        _long_paragraph("Repeated denial"),
        _long_paragraph("Blame shifting"),
        _long_paragraph("Changing the subject"),
        _long_paragraph("The gradual loss of confidence"),
    ]

    content_html = "".join(f"<p>{p}</p>" for p in paragraphs)

    import html
    escaped_content = html.escape(content_html)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Understanding Repeated Relationship Patterns</title>
        <link rel="alternate" href="{article_url}" />
        <content type="html">{escaped_content}</content>
      </entry>
    </feed>
    """


class BloggerScraperTests(unittest.TestCase):

    ARTICLE_URL = (
        "https://example.blogspot.com/2026/07/article.html"
    )

    def test_extracts_blogger_post_body(self):
        result = scraper._parse_html(make_article_html())

        self.assertEqual(
            result["title"],
            "Understanding Repeated Relationship Patterns",
        )
        self.assertGreater(scraper._word_count(result["body"]), 120)
        self.assertIn("Repeated denial", result["body"])
        self.assertIn("reasonable concerns", result["body"])

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

    def test_builds_blogger_atom_feed_url(self):
        self.assertEqual(
            scraper._feed_url_for_article(self.ARTICLE_URL),
            "https://example.blogspot.com/feeds/posts/default"
            "?alt=atom&max-results=500",
        )

    def test_feed_extractor_matches_exact_article_url(self):
        response = Mock()
        response.text = make_feed_xml(self.ARTICLE_URL)
        response.raise_for_status.return_value = None

        with patch.object(
            scraper.requests,
            "get",
            return_value=response,
        ):
            result = scraper._scrape_with_blogger_feed(self.ARTICLE_URL)

        self.assertIsNotNone(result)
        self.assertEqual(
            result["title"],
            "Understanding Repeated Relationship Patterns",
        )
        self.assertEqual(result["source"], "blogger_atom_feed")
        self.assertGreater(scraper._word_count(result["body"]), 120)

    def test_feed_does_not_match_a_different_post(self):
        response = Mock()
        response.text = make_feed_xml(
            "https://example.blogspot.com/2026/07/another-post.html"
        )
        response.raise_for_status.return_value = None

        with patch.object(
            scraper.requests,
            "get",
            return_value=response,
        ):
            result = scraper._scrape_with_blogger_feed(self.ARTICLE_URL)

        self.assertIsNone(result)

    def test_feed_summary_without_content_is_rejected(self):
        response = Mock()
        response.text = f"""
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Short summary</title>
            <link rel="alternate" href="{self.ARTICLE_URL}" />
            <summary type="html">Only a short summary.</summary>
          </entry>
        </feed>
        """
        response.raise_for_status.return_value = None

        with patch.object(
            scraper.requests,
            "get",
            return_value=response,
        ):
            result = scraper._scrape_with_blogger_feed(self.ARTICLE_URL)

        self.assertIsNone(result)

    def test_http_path_returns_usable_article(self):
        response = Mock()
        response.text = make_article_html()
        response.raise_for_status.return_value = None

        with patch.object(
            scraper.requests,
            "get",
            return_value=response,
        ):
            result = scraper._scrape_with_requests(self.ARTICLE_URL)

        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "requests_html")
        self.assertGreater(scraper._word_count(result["body"]), 120)

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

        with patch.object(
            scraper.requests,
            "get",
            return_value=response,
        ):
            result = scraper._scrape_with_requests(self.ARTICLE_URL)

        self.assertIsNone(result)

    def test_validation_rejects_too_few_words(self):
        data = {
            "title": "A short article",
            "body": (
                "A short paragraph with a few words.\n\n"
                "Another short paragraph with a few words.\n\n"
                "One more short paragraph with a few words."
            ),
        }

        valid, reason = scraper._validate_article(data)

        self.assertFalse(valid)
        self.assertIn("words", reason)

    def test_scrape_article_uses_feed_before_other_fallbacks(self):
        expected = {
            "title": "A complete article",
            "body": "\n\n".join(
                _long_paragraph(str(i)) for i in range(4)
            ),
            "source": "blogger_atom_feed",
        }

        with patch.object(
            scraper,
            "_scrape_with_blogger_feed",
            return_value=expected,
        ) as feed, patch.object(
            scraper,
            "_scrape_with_requests",
        ) as http, patch.object(
            scraper,
            "_scrape_with_playwright",
        ) as browser:
            result = scraper.scrape_article(self.ARTICLE_URL)

        self.assertEqual(result["source"], "blogger_atom_feed")
        feed.assert_called_once_with(self.ARTICLE_URL)
        http.assert_not_called()
        browser.assert_not_called()

    def test_scrape_article_falls_back_to_http(self):
        expected = {
            "title": "A complete article",
            "body": "\n\n".join(
                _long_paragraph(str(i)) for i in range(4)
            ),
            "source": "requests_html",
        }

        with patch.object(
            scraper,
            "_scrape_with_blogger_feed",
            return_value=None,
        ), patch.object(
            scraper,
            "_scrape_with_requests",
            return_value=expected,
        ), patch.object(
            scraper,
            "_scrape_with_playwright",
        ) as browser:
            result = scraper.scrape_article(self.ARTICLE_URL)

        self.assertEqual(result["source"], "requests_html")
        browser.assert_not_called()

    def test_scrape_article_fails_if_all_methods_are_incomplete(self):
        with patch.object(
            scraper,
            "_scrape_with_blogger_feed",
            return_value=None,
        ), patch.object(
            scraper,
            "_scrape_with_requests",
            return_value=None,
        ), patch.object(
            scraper,
            "_scrape_with_playwright",
            return_value={
                "title": "Incomplete",
                "body": "Only a fragment.",
            },
        ):
            with self.assertRaisesRegex(
                ValueError,
                "headline generator was not called",
            ):
                scraper.scrape_article(self.ARTICLE_URL)

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
            result = scraper.scrape_medium_post(self.ARTICLE_URL)

        self.assertEqual(result, expected)
        mocked.assert_called_once_with(self.ARTICLE_URL)

    def test_empty_url_is_rejected(self):
        with self.assertRaises(ValueError):
            scraper.scrape_article("")

    def test_non_http_url_is_rejected(self):
        with self.assertRaises(ValueError):
            scraper.scrape_article("not-a-url")


if __name__ == "__main__":
    unittest.main()
