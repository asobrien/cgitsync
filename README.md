cgitsync
========
Cgitsync is a small utility designed to keep mirrors defined in your
`cgitrepos` files syncronized. 


Quickstart
----------
Given a `cgitrepos` configuration:

```txt
section=my_org mirrors

repo.url=my_org/foo
repo.path=/srv/git/my_org/foo.git

repo.url=my_org/bar
repo.path=/srv/git/my_org/bar.git
```

You can easily clone (and subsequently update) mirrors with `cgitsync`:

```bash
cgitsync 'my_org mirrors'
```

This will clone *my_org/foo* and *my_org/bar* from github to `/srv/git/my_org/*`.

To update your mirrors, just run the above command again.


Installation
------------
1. Directly from source
    
    Cgitsync is a single python file with no external dependencies, you can
    install the latest version straight from source:

    ```bash
    curl -sL https://github.com/asobrien/cgitsync/archive/master.tar.gz | \
        tar --strip=1 -C /usr/local/bin -xvf - cgitsync/cgitsync.py
    ```

    You may want rename the file for convenience: 
    `mv /usr/local/bin/cgitsync.py /usr/local/bin/cgitsync`.


Configuration with `cgitrepos`
------------------------------
Cgitsync reads data from the specified sections in your `cgitrepos`
configuration file.

Custom keys, which may be useful when using the custom provider, can be
added to the repo, for example: `repo.foo=bar`.
