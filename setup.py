import os
from setuptools import setup


with open("README.md", "r") as fh:
    long_desc = fh.read()


def required(requirements_file):
    """ Read requirements file and remove comments and empty lines. """
    base_dir = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(base_dir, requirements_file), 'r') as f:
        requirements = f.read().splitlines()
        return [pkg for pkg in requirements
                if pkg.strip() and not pkg.startswith("#")]


setup(
    name='hivemind_bus_client',
    version='0.0.1a1',
    packages=['hivemind_bus_client'],
    package_data={
      '*': ['*.txt', '*.md']
    },
    include_package_data=True,
    install_requires=required('requirements.txt'),
    url='https://github.com/JarbasHiveMind/hivemind_websocket_client',
    license='Apache-2.0',
    author='JarbasAi',
    author_email='jarbasai@mailfence.com',
    description='Hivemind Websocket Client',
    long_description=long_desc,
    long_description_content_type="text/markdown",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',

        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ]
)
