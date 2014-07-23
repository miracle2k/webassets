import os
from pprint import pprint
from webassets.filter import Filter

class JSDepSort:

    def __init__(self, *args, **kwargs):
        self.search_path = kwargs.pop('search_path', [])
        if not isinstance(self.search_path, (list, tuple)):
            self.search_path = [self.search_path]
    
    def sort(self, contents):
        deps = map(self.parse_deps, map(lambda c: c[1], contents))

        content_map = {}
        for d, c in zip(deps, contents):
            content_map[c[1]] = {'deps':d, 'content':c}

        ordered_contents = []
        pre_visits = set()
        post_visits = set()

        for content in contents:
            path = content[1]
            deps = content_map[path]['deps']
            self.append_content(content, deps, content_map, ordered_contents, pre_visits, post_visits)
        
        return ordered_contents

    def read_contents(self, path):
        return open(path).read()

    def parse_deps(self, path):
            hunk = self.read_contents(path)

            dependencies = []

            lines = hunk.splitlines()
            for line in lines:
                line = line.strip()
                
                if line.startswith('//='):
                    directive = line[len('//='):].split()
                    if directive[0] == 'require':
                        dependencies.append(directive[1])

            return dependencies

    def append_content(self, content, deps, content_map, ordered_contents, pre_visits, post_visits):
        path = content[1]
        
        if path in post_visits:
            return

        pre_visits.add(path)

        for dep in deps:
            dep_path = self.resolve_dep(dep, content_map)
            if not dep_path:
                raise Exception(
                    'Could not resolve dependency "{}" of source'
                    ' file "{}"'.format(dep, path))

            if dep_path in pre_visits and not dep_path in post_visits:
                raise Exception(
                    'Circular dependency found: "{}" depends on {}'
                    .format(path, dep))


            self.append_content(content_map[dep_path]['content'], content_map[dep_path]['deps'], 
                        content_map, ordered_contents, pre_visits, post_visits)


        ordered_contents.append(content)

        post_visits.add(path)

    def resolve_dep(self, dep, content_map):
        if dep.startswith("/"):
            #We are an absolute path.  Why would you do this???
            if dep in content_map:
                return dep
            else:
                raise Exception('Dependency "{}" not in this bundle.'.format(dep))

        for search_path in self.search_path:
            path = os.path.join(search_path, dep)
            # print 'searching for dep {} at {}'.format(dep, path)
            if path in content_map:
                return path 
            
        raise Exception('Dependency "{}" not found in this bundle.'.format(dep))
        

