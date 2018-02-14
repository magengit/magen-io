# coding=utf-8
"""
Check versions of pip and python
"""
import sys
import pip

if sys.version_info < (3, 6, 3):
    sys.exit("Sorry, you need Python 3.6.3+")

pip_version = int(pip.__version__.replace(".", ""))
if pip_version < 901:
        sys.exit("Sorry, you need pip 9.0.1+")
