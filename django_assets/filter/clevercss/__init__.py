"""Converts `CleverCSS <http://sandbox.pocoo.org/clevercss/>`_ markup to 
real CSS.

If you want to combine it with other CSS filters, make sure this one runs 
first.
"""

import clevercss

def apply(_in, out):
	out.write(clevercss.convert(_in.read()))