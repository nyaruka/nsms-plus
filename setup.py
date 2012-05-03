from setuptools import setup, find_packages

setup(
    name='nsms_plus',
    version=__import__('nsms_plus').__version__,
    license="BSD",

    install_requires = [
    ],

    description="Nyaruka specific customazations to nsms",
    long_description=open('README.md').read(),

    author='Nyaruka Ltd',
    author_email='code@nyaruka.com',

    url='http://github.com/nyaruka/nsms-plus',
    download_url='http://github.com/nyaruka/nsms-plus/downloads',

    include_package_data=True,

    packages=find_packages(),

    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ]
)
