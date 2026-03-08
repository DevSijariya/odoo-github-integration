{
    'name': 'GitHub Integrator',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Integrate GitHub with Odoo for repository and issue tracking',
    'description': """
        GitHub Integrator
        =================

        This module connects GitHub with Odoo so teams can sync and manage:
        - Repositories
        - Branches
        - Commits
        - Issues
        - Collaborators

        It also supports repository to project linkage for better operational tracking.
        """,
    'author': 'Sanskar Sijariya',
    'maintainer': 'Sanskar Sijariya',
    'license': 'LGPL-3',
    'data': [
        'security/ir.model.access.csv',
        'views/github_integrator.xml',
        'views/github_commit.xml',
        'views/github_issue.xml',
        'views/github_repository.xml',
        'views/menus.xml'
    ],
    'price': 5.0,
    'currency': 'USD',
    'application': True,
    'installable': True,
    'support': 'sanskarsijariya80@gmail.com',
    "images": [
        "static/description/icon.jpeg"
    ],
    'images': 'static/description/icon.jpeg',
    'depends': ['base', 'project'],
}
