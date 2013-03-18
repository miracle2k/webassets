from __future__ import print_function
from __future__ import print_function
from __future__ import print_function
from __future__ import print_function
from __future__ import print_function
# Import assets configuration
from assets import bundle

print('Content-Type: text/html')
print('')
print('''
<html>
   <head>''')
for url in bundle.urls():
    print('<link rel="stylesheet" type="text/css" href="%s" />' % url)
print('''
   </head>
   <body>
      Hello World!
   </body>
</html>
''')

