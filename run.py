from app import create_app, db
from app.models import User, Delegate, Payment

app = create_app()


@app.shell_context_processor
def make_shell_context():
    """Add database models to Flask shell context"""
    return {
        'db': db,
        'User': User,
        'Delegate': Delegate,
        'Payment': Payment
    }


if __name__ == '__main__':
    app.run(debug=True)
