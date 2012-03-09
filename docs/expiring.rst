.. _expiry:


URL Expiry (cache busting)
==========================

For beginners
-------------

You are using ``webassets`` because you care about the performance of your
site. For the same reason, you have configured your web server to send out
your media files with a so called *far future expires* header: Your web server
sets the ``Expires`` header to some date many years in the future. Your user's
browser will never spend any time trying to retrieve an updated version.

.. note::

   Of course, the user's browser will already use the ``Etag`` and
   ``Last-Modified/If-Modified-Since`` to avoid downloading content it has
   already cached, and if your web server isn't misconfigured entirely, this
   will work. The point of *far future expires* is to get rid of **even**
   those requests which would return only a ``304 Not Modified`` response.

What if you actually deploy an update to your site? Now you need to convince
the browser to download new versions of your assets after all, but you have
just told it not to bother to check for new versions. You work around this by
*modifying the URL with which the asset is included*. There are two distinct
ways to so:

1) Append a version identifier as a querystring::

    http://www.example.org/media/print.css?acefe50

2) Add a version identifier to the actual filename::

    http://www.example.org/media/print.acefe50.css

How webassets helps you do this is explained in the sections below.

.. note::

    Even if you are not using *far future expires* headers, you might still find
    ``webassets`` expiry features useful to navigate around any funny browser
    caching behaviour that might require a ``Shift``-reload.


What is the version of a file
-----------------------------

To expire an URL, it is modified with a version identifier. What is this
identifier? By default, ``webassets`` will create an MD5-hash of the file
contents, and use the first few characters as the file version. ``webassets``
also allows you to use the *last modified* timestamp of the file. You can
configure this via the ``versions`` option::

    env = Environment(...)
    env.versions = 'hash'         # the default
    env.versions = 'hash:32'      # use the full md5 hash
    env.versions = 'timestamp'    # use the last modified timestamp

It is generally recommended that you use a hash as the version, since it will
remain the same as long as the content does not change, regardless of any
filesystem metadata, which can change for any number of reasons.


Expire using a querystring
--------------------------

``webassets`` will automatically add the version as a querystring to the urls
it generates, by virtue of the ``url_expire`` option defaulting to ``True``.
If you want to be explicit::

    env = Environment(...)
    env.url_expire = True

There is nothing else you need to do here. The URLs that are generated might
look like this::

    /media/print.css?acefe50

However, while the default, expiring with a querystring is not be the best
option:


Expire using the filename
-------------------------

Adding the version as a querystring has two problems. First, it may not always
be a browser that implements caching through which we need to bust. It is said
that certain (possibly older) proxies do ignore the querystring with respect
to their caching behavior.

Second, in certain more complex deployment scenarios, where you have multiple
frontend and/or multiple backend servers, an upgrade is anything but
instantaneous. You need to be able to serve both the old and the new version
of your assets at the same time. See for example how this affects you `when
using Google App Engine <http://bjk5.com/post/4918954974/js-css-packaging-to-minimize-requests-and-randomly-evil>`_.

To expire using the filename, you add a ``%(version)s`` placeholder to your
bundle output target::

    bundle = Bundle(..., output='screen.%(version)s.css')

The URLs that are generated might look like this::

    /media/screen.acefe50.css

.. note::

   ``webassets`` will use this modified filename for the actual output files
   it writes to disk, as opposed to just modifying the URL it generates. You
   do not have to configure your web server to do any rewriting.


About manifests
---------------

.. note::

   This is mostly an advanced feature, and you might not have to bother with
   it at all.

``webassets`` supports Environment-wide *manifests*. A manifest remembers the
current version of every bundle. What is this good for?

1) Speed. Calculating a hash can be expensive. Even if you are using
   timestamp-based versions, that still means a stat-request to your disk.

   .. note::

      Note that even without a manifest, ``webassets`` will cache the version
      in memory. It will only need to be calculated once per process. However,
      if you have *many* bundles, and a very busy site, a manifest will allow
      you to both skip calculating the version (e.g. creating a hash), as well
      as read the versions of all bundles into memory at once.

   .. note::

      If you are using automatic building, all of this is mostly not true. In
      order to determine whether a rebuild is required, ``webassets`` will need
      to check the timestamps of all files involved in any case. It goes
      without saying that using automatic building on a production site is a
      convenience feature for small sites, and at odds with counting paper
      clips in the form of filesystem ``stat`` calls.

2) Making it possible to know the version in the first place.

   Depending on your configuration and deployment, consider that it might not
   actually be possible for ``webassets`` to know what the version is.

   If you are using a hash-based version, and your bundle's output target has
   a placeholder, there is no way to know what the version is, *unless* is
   has been written to a manifest during the build process.

   The timestamp-based versioning mechanism can actually look at the source
   files to determine the version. But, in more complex deployments, the source
   files might not actually be available to read - they might be on a
   completely different server altogether.

   A manifest allows version information to be persisted.


In practice, by default the version information will be written to the cache.
You can explicitly request this behaviour be setting the ``manifest`` option::

    env = Environment(...)
    env.manifest = 'cache'

In a simple setup, where you are separately building on your local machine
during development, and building on the web server for production (maybe via
the automatic building feature, enabled by default), this is exactly would
you want. Don't worry about it.

There is a specific deployment scenario where you want to prebuild your bundles
locally, and for either of the two reasons above want to include  the version
data pre-made when you deploy your app to the web server. In such a case, it
is not helpful to have the versions stored in the cache. Instead, ``webassets``
provides a manifest type that writes all information to a single file::

    env = Environment(...)
    env.manifest = 'file'
    env.manifest = 'file:/tmp/manifest.to-be-deployed'  # explict filename

You can then just copy this one file to the web server, and ``webassets``
will know all about the versions without having to consult the media files.

.. note::

   The file is a pickled dict.
