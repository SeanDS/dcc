Developer guide
===============

Set up the development environment
----------------------------------

First fork the git repository at https://git.ligo.org/sean-leavey/dcc and clone it on
your computer:

.. code-block:: text

    $ git clone <url for forked repository>

then install the package as editable, alongside the developer dependencies:

.. code-block:: text

     $ cd /path/to/cloned/dcc/repository
     $ pip install -e .[dev]

The project uses `pre-commit <https://pre-commit.com/>`__ to perform checking and code
formatting as part of the git commit process. To initialise this, run:

.. code-block:: text

    $ pre-commit install

Development should be done on branches referenced from ``develop``. Check out the
``develop`` branch with ``git checkout develop``.

Make your changes, preferably on a separate branch, then commit. The pre-commit hooks
will apply Black formatting to the code, check a few things, and potentially flag
problems. Fix the problems and commit again, pushing changes to your remote fork and
opening a pull request on GitLab.

Building the documentation
--------------------------

The documentation is built with `Sphinx <https://www.sphinx-doc.org/>`__. To build, run:

.. code-block:: text

    $ cd /path/to/cloned/dcc/repository/docs
    $ make html

This builds HTML formatted documentation. Other formats are available (type ``make`` to
see what's available), but not typically used.

To view the built documentation, open the ``index.html`` file in ``docs/build/html``.

Release steps
-------------

Preliminary steps
~~~~~~~~~~~~~~~~~

#. Update the API documentation with any changes to the Python modules.
#. Update ``README.md`` with any new features added since the previous release.
#. Ensure the CLI's own help strings are consistent with those in the documentation.

Creating a tagged release
~~~~~~~~~~~~~~~~~~~~~~~~~

#. Check out a release branch with the intended new version number with ``git checkout
   -b release/X.Y.Z``, build the project (including documentation) and check it all
   works.
#. Summarise changes in ``CHANGELOG`` (hint: use ``git log dcc-X.Y.Z..HEAD`` where
   ``X.Y.Z`` was the previous tagged release) and commit.
#. Tag the release branch with ``git tag -a dcc-X.Y.Z``, typing "DCC vX.Y.Z" as the
   release message.
#. Check out the ``develop`` branch again, and merge the release branch with ``git merge
   --no-ff release/X.Y.Z``.
#. Check out the ``master`` branch again, and merge the release branch with ``git merge
   --no-ff release/X.Y.Z``.
#. Push the branches and tags to the remote with ``git push develop``, ``git push
   master`` and ``git push --tags``.

Uploading to PyPI
~~~~~~~~~~~~~~~~~

The following instructions are based on
https://packaging.python.org/en/latest/tutorials/packaging-projects/.

.. note::

    Uploading to `PyPI <https://pypi.org/>`__ requires an account that is a maintainer of
    the `dcc project <https://pypi.org/project/dcc>`__ there.

#. Make sure you have the latest version of the ``build`` library by running ``pip
   install --upgrade build``. Build an sdist and wheel using ``python -m build`` from
   the project directory. Check the ``dist`` directory contains a
   ``dcc-X.Y.Z-py3-none-any.whl`` and ``dcc-X.Y.Z.tar.gz`` files. If the filenames do
   not contain only the tagged version (but rather also some git commit hash suffix),
   check that you're on a branch level with the tagged branch.
#. Check your ``twine`` package is up-to-date using ``pip install --upgrade twine``.
#. (Optional) upload a test release to the PyPI test server using ``twine upload
   --repository testpypi dist/*`` and verify everything looks ok at
   https://test.pypi.org/project/dcc-YOUR-USERNAME-HERE.
#. Upload the release to `PyPI <https://pypi.org/>`__ using ``twine upload dist/*`` and
   verify everything looks ok at https://pypi.org/project/dcc.
