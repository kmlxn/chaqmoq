import markdown2
from jinja2 import Environment, PackageLoader, select_autoescape
from slugify import slugify
from iteration_utilities import unique_everseen
import os
from livereload import Server
import sys
from distutils.dir_util import copy_tree
import shutil
import config

env = Environment(
    loader=PackageLoader(__name__, 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

class Post:
    def __init__(self, content, url, slug, meta):
        self.content = content
        self.url = url
        self.slug = slug
        self.date = meta.get('date')
        self.title = meta.get('title') or 'Untitled'
        self.summary = meta.get('summary')
        if meta.get('tags'):
            self.tags = [
                {
                    'title': tag.strip(),
                    'slug': slugify(tag.strip()),
                    'url': '/tags/' + slugify(tag.strip())
                } for tag in meta['tags'].split(',')
            ]
        else:
            self.tags = []

def deduplicate_tags(tags):
    return list(unique_everseen(tags, lambda tag: tag['slug']))

def paginate(items, page_size):
    return [items[i:i + page_size] for i in range(0, len(items), page_size)]

def get_post_contents():
    post_folders = [d for d in os.listdir('content') if os.path.isdir('content/' + d)]

    posts = []
    for post_folder in post_folders:
        src_post_path = os.path.join('content', post_folder, 'index.md')
        html = markdown2.markdown_path(src_post_path, extras=["metadata"])
        url = '/' + post_folder
        slug = post_folder
        post = Post(html, url, slug, html.metadata)
        posts.append(post)

    return posts

def make_post_pages(posts):
    global env
    template = env.get_template('post.html')

    # copy other files
    post_folders = [d for d in os.listdir('content') if os.path.isdir('content/' + d)]
    for post_folder in post_folders:
        os.makedirs(os.path.join("output", post_folder), exist_ok=True)
        post_dir_path = os.path.join("content", post_folder)
        post_files = os.listdir(post_dir_path)
        files_to_copy = [file for file in post_files if file != 'index.md']
        for file in files_to_copy:
            shutil.copy2(os.path.join(post_dir_path, file), os.path.join('output', post_folder))

    for post in posts:
        os.makedirs(os.path.join('output', post.slug), exist_ok=True)
        with open(os.path.join('output', post.slug, 'index.html'), 'w') as f:
            page = template.render(post=post, site_title=config.SITE_TITLE)
            f.write(page)

    return posts

def get_tags(posts):
    tags_from_posts = [tag for post in posts for tag in post.tags]
    tags = deduplicate_tags(tags_from_posts)

    return tags

def make_pagination(pages, page_index, url_prefix = '/'):
    pagination = [
        {
            'number': index + 1,
            'url': url_prefix + str(index + 1 if index > 0 else ''),
            'active': index == page_index,
        }
        for index, _ in enumerate(pages)
    ] if len(pages) > 1 else []
    

    page = pagination[page_index] if pagination else {}
    pagination = pagination
    next_page = pagination[page_index + 1] if page_index < len(pagination) - 1 else {}
    prev_page = pagination[page_index - 1] if pagination and page_index > 0 else {}

    return {
        'page': page,
        'pages': pagination,
        'next_page': next_page,
        'prev_page': prev_page,
    }

def make_index_pages(posts, tags):
    global env
    template = env.get_template('index.html')

    if config.POSTS_PER_PAGE:
        pages = paginate(posts, config.POSTS_PER_PAGE)
    else:
        pages = [posts]

    for page_index, page in enumerate(pages):
        index_page = template.render(
            posts=page,
            tags=tags,
            site_title=config.SITE_TITLE,
            **make_pagination(pages, page_index)
        )

        if page_index == 0:
            path = 'output/index.html'
        else:
            os.makedirs(f'output/{page_index + 1}', exist_ok=True)
            path = f'output/{page_index + 1}/index.html'

        with open(path, 'w') as f:
            f.write(index_page)


def make_tag_pages(posts, tags):
    global env
    template = env.get_template('tag.html')

    for tag in tags:
        posts_for_tag = [post for post in posts if next(filter(lambda t: t['slug'] == tag['slug'], post.tags), None)]

        if config.POSTS_PER_PAGE:
            pages = paginate(posts_for_tag, config.POSTS_PER_PAGE)
        else:
            pages = [posts_for_tag]
        
        for page_index, page in enumerate(pages):
            index_page = template.render(
                tag=tag,
                posts=page,
                tags=tags,
                site_title=config.SITE_TITLE,
                **make_pagination(pages, page_index, tag['url'] + '/'),
            )

            if page_index == 0:
                os.makedirs(f'output/tags/{tag["slug"]}', exist_ok=True)
                path = f'output/tags/{tag["slug"]}/index.html'
            else:
                os.makedirs(f'output/tags/{tag["slug"]}/{page_index + 1}', exist_ok=True)
                path = f'output/tags/{tag["slug"]}/{page_index + 1}/index.html'

            with open(path, 'w') as f:
                f.write(index_page)

def run():
    try:
        shutil.rmtree('output')
    except FileNotFoundError:
        pass

    os.makedirs("output", exist_ok=True)
    copy_tree("templates/static", "output/static")

    posts = get_post_contents()
    tags = get_tags(posts)

    make_post_pages(posts)
    make_index_pages(posts, tags)
    make_tag_pages(posts, tags)

if __name__ == "__main__":
    run()
    if len(sys.argv) > 1 and sys.argv[1] == 'serve':
        server = Server()
        server.watch('content/*.md', run)
        server.serve(root='output')