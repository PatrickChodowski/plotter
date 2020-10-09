from setuptools import setup

setup(
    name='chartz',
    url='https://github.com/PatrickChodowski/plotter',
    author='Patrick Chodowski',
    author_email='chodowski.patrick@gmail.com',
    packages=['chartz'],
    package_data={'chartz': ['chartz_templates/*.html',
                              'chartz_static/*.js',
                              'chartz_static/*.yaml',
                              'chartz_static/*.css',
                              'chartz_static/bootstrap/css/*.css',
                              'chartz_static/bootstrap/css/*.map',
                              'chartz_static/bootstrap/js/*.js',
                              'chartz_static/bootstrap/js/*.map']},
    install_requires=['flask', 'bokeh', 'google-cloud-bigquery','google-cloud-storage' ,'pandas', 'pyyaml', 'sqlalchemy'],
    # *strongly* suggested for sharing
    version='0.4.7',
    license='MIT',
    description='Flask module allowing to build dashboards for data defined in single yml files',
    long_description=open('README.rst').read(),
)