import markdown2
from jinja2 import Environment, PackageLoader, select_autoescape
from slugify import slugify
from iteration_utilities import unique_everseen
import os
from livereload import Server
import sys
from distutils.dir_util import copy_tree
import shutil
from datetime import datetime
import config


env = Environment(
    loader=PackageLoader(__name__, 'templates'),
    autoescape=select_autoescape(['html', 'xml']),
)


def wrap_page(content, url, slug, meta):
    return {
        'content': content,
        'url': url,
        'slug': slug,
        'title': meta.get('title', 'Untitled'),
        'summary': meta.get('summary'),
        'order': int(meta.get('order')) if meta.get('order') else 0,
        'image': meta.get('image'),
    }


def wrap_post(content, url, slug, meta):
    return {
        'content': content,
        'url': url,
        'slug': slug,
        'date': meta.get('date'),
        'title': meta.get('title', 'Untitled'),
        'summary': meta.get('summary'),
        'image': meta.get('image'),
        'tags': [
            {
                'title': tag.strip(),
                'slug': slugify(tag.strip()),
                'url': '/tags/' + slugify(tag.strip())
            } for tag in meta['tags'].split(',')
        ] if meta.get('tags') else []
    }


def deduplicate_tags(tags):
    return list(unique_everseen(tags, lambda tag: tag['slug']))


def group_by(items, page_size):
    return [items[i:i + page_size] for i in range(0, len(items), page_size)]


def get_posts():
    path = 'content/posts'
    post_folders = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]

    posts = []
    for post_folder in post_folders:
        src_post_path = os.path.join(path, post_folder, 'index.md')
        html = markdown2.markdown_path(src_post_path, extras=["metadata"])
        post = wrap_post(
            content=html,
            url='/' + post_folder,
            slug=post_folder,
            meta=html.metadata
        )
        posts.append(post)

    get_date = lambda post: post['date'] or datetime.strptime(post['date'], '%Y-%m-%d')
    
    return sorted(posts, key=get_date)


def get_pages():
    path = 'content/pages'
    page_folders = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]

    pages = []
    for page_folder in page_folders:
        src_page_path = os.path.join(path, page_folder, 'index.md')
        html = markdown2.markdown_path(src_page_path, extras=["metadata"])
        page = wrap_page(
            content=html,
            url='/' + page_folder,
            slug=page_folder,
            meta=html.metadata
        )
        pages.append(page)

    return sorted(pages, key=lambda p: p['order'])


def make_posts_html(posts, pages):
    global env
    template = env.get_template('post.html')

    post_folders = [d for d in os.listdir('content/posts')
        if os.path.isdir(os.path.join('content/posts', d))]

    for post_folder in post_folders:
        os.makedirs(os.path.join("output", post_folder), exist_ok=True)
        post_dir_path = os.path.join("content/posts", post_folder)
        post_files = os.listdir(post_dir_path)
        files_to_copy = [file for file in post_files if file != 'index.md']

        for file in files_to_copy:
            shutil.copy2(
                os.path.join(post_dir_path, file),
                os.path.join('output', post_folder)
            )

    for post in posts:
        os.makedirs(os.path.join('output', post['slug']), exist_ok=True)
        with open(os.path.join('output', post['slug'], 'index.html'), 'w') as f:
            page = template.render(
                post=post,
                meta_description=config.META_DESCRIPTION,
                site_title=config.SITE_TITLE,
                pages=pages
                )
            f.write(page)

    return posts


def make_pages_html(pages):
    global env
    template = env.get_template('page.html')

    page_folders = [d for d in os.listdir('content/pages')
        if os.path.isdir(os.path.join('content/pages', d))]

    for page_folder in page_folders:
        os.makedirs(os.path.join("output", page_folder), exist_ok=True)
        page_dir_path = os.path.join("content/pages", page_folder)
        page_files = os.listdir(page_dir_path)
        files_to_copy = [file for file in page_files if file != 'index.md']

        for file in files_to_copy:
            shutil.copy2(
                os.path.join(page_dir_path, file),
                os.path.join('output', page_folder)
            )

    for page in pages:
        os.makedirs(os.path.join('output', page['slug']), exist_ok=True)
        with open(os.path.join('output', page['slug'], 'index.html'), 'w') as f:
            page = template.render(
                page=page,
                pages=pages,
                meta_description=config.META_DESCRIPTION,
                site_title=config.SITE_TITLE,
            )
            f.write(page)

    return pages


def get_tags(posts):
    tags_from_posts = [tag for post in posts for tag in post['tags']]
    tags = deduplicate_tags(tags_from_posts)

    return tags


def make_pagination(groups, group_index, url_prefix = '/'):
    pagination = [
        {
            'number': index + 1,
            'url': url_prefix + str(index + 1 if index > 0 else ''),
            'active': index == group_index,
        }
        for index, _ in enumerate(groups)
    ] if len(groups) > 1 else []
    

    pagination = pagination
    next_group = pagination[group_index + 1] if group_index < len(pagination) - 1 else {}
    prev_group = pagination[group_index - 1] if pagination and group_index > 0 else {}

    return {
        'pagination': pagination,
        'next_group': next_group,
        'prev_group': prev_group,
    }


def make_index_html(posts, pages, tags):
    global env
    template = env.get_template('index.html')

    if config.POSTS_PER_PAGE:
        grouped_posts = group_by(posts, config.POSTS_PER_PAGE)
    else:
        grouped_posts = [posts]

    for group_index, group in enumerate(grouped_posts):
        index_page = template.render(
            posts=group,
            tags=tags,
            meta_description=config.META_DESCRIPTION,
            site_title=config.SITE_TITLE,
            site_subtitle=config.SITE_SUBTITLE,
            pages=pages,
            **make_pagination(grouped_posts, group_index)
        )

        if group_index == 0:
            path = 'output/index.html'
        else:
            os.makedirs(f'output/{group_index + 1}', exist_ok=True)
            path = f'output/{group_index + 1}/index.html'

        with open(path, 'w') as f:
            f.write(index_page)


def make_tag_html(posts, tags, pages):
    global env
    template = env.get_template('tag.html')

    for tag in tags:
        is_needed_tag = lambda t: t['slug'] == tag['slug']
        posts_for_tag = [
            post for post in posts if list(filter(is_needed_tag, post['tags']))
        ]

        if config.POSTS_PER_PAGE:
            groups = group_by(posts_for_tag, config.POSTS_PER_PAGE)
        else:
            groups = [posts_for_tag]
        
        for page_index, page in enumerate(groups):
            index_page = template.render(
                tag=tag,
                posts=page,
                tags=tags,
                pages=pages,
                meta_description=config.META_DESCRIPTION,
                site_title=config.SITE_TITLE,
                **make_pagination(groups, page_index, tag['url'] + '/'),
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

    posts = get_posts()
    pages = get_pages()
    tags = get_tags(posts)

    make_posts_html(posts, pages)
    make_pages_html(pages)
    make_tag_html(posts, tags, pages)
    make_index_html(posts, pages, tags)


if __name__ == "__main__":
    run()
    if len(sys.argv) > 1 and sys.argv[1] == 'serve':
        server = Server()
        server.watch('content/*.md', run)
        server.serve(root='output')