import markdown2
from jinja2 import Environment, PackageLoader, select_autoescape
from slugify import slugify
from iteration_utilities import unique_everseen
import os
from os.path import join
from livereload import Server
import sys
import shutil
from datetime import datetime
import config


def abs_path(path):
    package_dir = os.path.dirname(os.path.abspath(__file__))
    return join(package_dir, path)

all_pages_folder = abs_path('content/pages')
all_posts_folder = abs_path('content/posts')
output_folder = abs_path('output')
tags_output_folder = abs_path('output/tags')


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
    global all_posts_folder

    post_folder_names = [d for d in os.listdir(all_posts_folder)
        if os.path.isdir(join(all_posts_folder, d))]

    posts = []
    for post_folder_name in post_folder_names:
        src_post_path = join(all_posts_folder, post_folder_name, 'index.md')
        html = markdown2.markdown_path(src_post_path, extras=["metadata"])
        post = wrap_post(
            content=html,
            url='/' + post_folder_name,
            slug=post_folder_name,
            meta=html.metadata
        )
        posts.append(post)

    get_date = lambda post: post['date'] or datetime.strptime(post['date'], '%Y-%m-%d')
    
    return sorted(posts, key=get_date)


def get_pages():
    global all_pages_folder

    page_folder_names = [d for d in os.listdir(all_pages_folder)
        if os.path.isdir(join(all_pages_folder, d))]

    pages = []
    for page_folder_name in page_folder_names:
        page_path = join(all_pages_folder, page_folder_name, 'index.md')
        html = markdown2.markdown_path(page_path, extras=["metadata"])
        page = wrap_page(
            content=html,
            url='/' + page_folder_name,
            slug=page_folder_name,
            meta=html.metadata
        )
        pages.append(page)

    return sorted(pages, key=lambda p: p['order'])


def make_posts_html(posts, pages):
    global env, all_posts_folder, output_folder
    template = env.get_template('post.html')
    
    post_folder_names = [d for d in os.listdir(all_posts_folder)
        if os.path.isdir(join(all_posts_folder, d))]

    for post_folder_name in post_folder_names:
        generated_folder = join(output_folder, post_folder_name)
        os.makedirs(generated_folder, exist_ok=True)
        post_folder = join(all_posts_folder, post_folder_name)
        post_files = os.listdir(post_folder)
        files_to_copy = [file for file in post_files if file != 'index.md']

        for file in files_to_copy:
            shutil.copy2(
                join(post_folder, file),
                generated_folder
            )

    for post in posts:
        with open(join(output_folder, post['slug'], 'index.html'), 'w') as f:
            page = template.render(
                post=post,
                meta_description=config.META_DESCRIPTION,
                site_title=config.SITE_TITLE,
                pages=pages,
            )
            f.write(page)

    return posts


def make_pages_html(pages):
    global env, all_pages_folder, output_folder
    template = env.get_template('page.html')

    page_folder_names = [d for d in os.listdir(all_pages_folder)
        if os.path.isdir(join(all_pages_folder, d))]

    for page_folder_name in page_folder_names:
        os.makedirs(join(output_folder, page_folder_name), exist_ok=True)
        page_folder = join(all_pages_folder, page_folder_name)
        page_files = os.listdir(page_folder)
        files_to_copy = [file for file in page_files if file != 'index.md']

        for file in files_to_copy:
            shutil.copy2(
                join(page_folder, file),
                join(output_folder, page_folder_name)
            )

    for page in pages:
        with open(join(output_folder, page['slug'], 'index.html'), 'w') as f:
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
    global env, output_folder
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
            path = join(output_folder, 'index.html')
        else:
            os.makedirs(join(output_folder, str(group_index + 1)), exist_ok=True)
            path = join(output_folder, str(group_index + 1), 'index.html')

        with open(path, 'w') as f:
            f.write(index_page)


def make_tag_html(posts, tags, pages):
    global env, output_folder
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
                os.makedirs(join(tags_output_folder, tag['slug']), exist_ok=True)
                path = join(tags_output_folder, tag['slug'], 'index.html')
            else:
                os.makedirs(join(tags_output_folder, tag['slug'], str(page_index + 1)), exist_ok=True)
                path = join(tags_output_folder, tag['slug'], str(page_index + 1), 'index.html')

            with open(path, 'w') as f:
                f.write(index_page)


def run():
    os.makedirs(all_pages_folder, exist_ok=True)
    os.makedirs(all_posts_folder, exist_ok=True)
    shutil.copytree(
        abs_path('templates/static'),
        abs_path('output/static'),
        dirs_exist_ok=True
    )

    posts = get_posts()
    pages = get_pages()
    tags = get_tags(posts)

    make_posts_html(posts, pages)
    make_pages_html(pages)
    make_tag_html(posts, tags, pages)
    make_index_html(posts, pages, tags)


def _init_livereload_patch():
    """
    Select compatible event loop for Tornado 5+.
     As of Python 3.8, the default event loop on Windows is `proactor`,
    however Tornado requires the old default "selector" event loop.
    As Tornado has decided to leave this to users to set, MkDocs needs
    to set it. See https://github.com/tornadoweb/tornado/issues/2608.
    """
    if sys.platform.startswith("win") and sys.version_info >= (3, 8):
        import asyncio
        try:
            from asyncio import WindowsSelectorEventLoopPolicy
        except ImportError:
            pass  # Can't assign a policy which doesn't exist.
        else:
            if not isinstance(asyncio.get_event_loop_policy(), WindowsSelectorEventLoopPolicy):
                asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())


if __name__ == "__main__":
    run()
    if len(sys.argv) > 1 and sys.argv[1] == 'serve':
        _init_livereload_patch()
        server = Server()
        server.watch(join(all_pages_folder, '*/*'), run)
        server.watch(join(all_posts_folder, '*/*'), run)
        server.serve(root=output_folder)