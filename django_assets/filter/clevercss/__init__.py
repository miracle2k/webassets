"""Converts CleverCSS markup to real CSS.

If you want to combine this with other CSS filters, make sure this
one runs first.

For more information about CleverCSS, see:
    http://sandbox.pocoo.org/clevercss/
"""

import clevercss

def apply(_in, out):
	out.write(clevercss.convert(_in.read()))