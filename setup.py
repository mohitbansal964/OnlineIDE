from setuptools import setup
import sys

if sys.version_info < (3,):
    sys.exit('Sorry, Python 3 is required for OnlineIDE.')

with open('Readme.md', encoding="utf8") as f:
    readme = f.read()

with open('LICENSE.txt') as f:
    license = f.read()

with open('requirements.txt') as f:
    reqs = f.read()

setup(
    name='OnlineIDE',
    author= 'Mohit Bansal',
    author_email= 'bansalmohit72@gmail.com',
    version='0.1.0',
    url= "https://mohit-onlineide.herokuapp.com/",
    description='Online Compiler',
    long_description=readme,
    license=license,
    install_requires=reqs.strip().split('\n'),
    include_package_data=True,
)