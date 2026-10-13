import unittest
from tools.article_body_summary import article_body_summary

class ArticleBodySummaryTests(unittest.TestCase):
    def test_explicit_body_beats_mismatched_metadata_and_recommendations(self):
        body = '''<meta property="og:description" content="Sidebar plasma news">
        <aside><p>Unrelated sidebar article about fusion science and funding.</p></aside>
        <article><p>Railway engineers are testing an ultrasonic inspection robot for hollow axles.</p>
        <section class="related"><p>Unrelated scientific standard and other recommendations must stay excluded.</p></section></article>'''
        self.assertEqual(article_body_summary(body), 'Railway engineers are testing an ultrasonic inspection robot for hollow axles.')
    def test_unscoped_paragraphs_are_not_trusted(self):
        self.assertEqual(article_body_summary('<p>Unrelated sidebar article about fusion science and funding.</p>'), '')
    def test_body_container_and_metadata_fallback(self):
        self.assertIn('Body', article_body_summary('<div class="article-content"><p>Body paragraph with enough characters to be a meaningful excerpt.</p></div>'))
        self.assertEqual(article_body_summary('<meta name="description" content="Actual article description">'), 'Actual article description')
