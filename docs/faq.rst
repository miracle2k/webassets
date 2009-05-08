FAQ
---

Relative URLs in my CSS code break if the merged asset is written to a different location than the source files. How do I fix this?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the builtin :ref:`cssrewrite <filters-cssrewrite>` filter which 
will transparently fix ``url()`` instructions in CSS files on the fly.