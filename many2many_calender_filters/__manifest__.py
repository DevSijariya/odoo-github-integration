{

 "name": "Odoo Github Integrator",
    "version": "18.0.1.0.0",
    "summary": "Project-based calendar filters with dependent assignee (Many2many) filters",
    "description": """
        This module extends the Project Task calendar view by adding:
        - A Project (Many2one) calendar filter
        - A dependent Assignee (Many2many) calendar filter
        - Automatic synchronization of assignees based on selected projects
        - User-specific filter persistence

        Selecting a project dynamically updates available assignees in the calendar.
    """,
    "category": "Project",
    "author": "Sanskar Sijariya",
    "license": "LGPL-3",

    'depends': ['base','project'],
    'images': 'static/description/icon.png',
    'data': [
        'security/ir.model.access.csv',
        'views/assignee_view.xml'
    ],
    "images": [
        "static/description/icon.png"
    ],
    
    'application': True,
    'installable': True,
    "support": "sanskarsijariya80@gmail.com",
    "price": 12.0,
    "currency": "USD",
}
