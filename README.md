# Chaqmoq - simple static site generator written in Python 3

Python >= 3.8 required.

0. `pip install -r requirements.txt`
1. Add folders files inside `content/posts` folder. Inside each folder add `index.md`. These will be your blog posts. You can add image, tags, date published, title to your posts.
2. Add folders files inside `content/pages` folder. Inside each folder add `index.md`. These will be your pages. You can add image, title to your pages.
3. run `python main.py`
4. Static files should appear in `output` folder. This is your static website.
5. To enable serving and reloading website while editing posts instead of `python main.py` run `python main.py serve`
6. To modify template change files inside `templates` folder.
7. There are `POSTS_PER_PAGE`, `SITE_TITLE`, `SITE_SUBTITLE`, `META_DESCRIPTION` setting inside `config.py`.