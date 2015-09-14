"""A Jupyter Checkpoints implementation using git.

- create-checkpoint = commit
- restore-checkpoint = git checkout
- list-checkpionts = git log
"""

import os
import pipes
from subprocess import check_output, CalledProcessError
from textwrap import indent

import dateutil.parser
parse_date = dateutil.parser.parse

from traitlets import Integer, Bool
from notebook.services.contents.filecheckpoints import FileCheckpoints
from notebook.services.contents.tz import utcnow

class GitCheckpoints(FileCheckpoints):
    
    max_checkpoints = Integer(5, config=True,
        help="The limit of how many checkpoints to show for a file."
    )
    create_commits = Bool(True, config=True,
        help="Whether creating checkpoints makes commits or just adds to the staging area."
    )
    
    def _in_git(self, path):
        try:
            self._git('log -1 --oneline', path)
        except CalledProcessError:
            return False
        else:
            return True
    
    def _git(self, args, path=None, include_file=True):
        """Run a git command on a file"""
        if isinstance(args, str):
            args = args.split()
        cmd = ['git'] + args
        cwd = self.root_dir
        if path:
            os_path = self._get_os_path(path)
            parent, name = os.path.split(os_path)
            cwd = parent
            if include_file:
                cmd.append(name)
        self.log.debug("[%s]> %s", cwd, ' '.join(pipes.quote(s) for s in cmd))
        try:
            out = check_output(cmd, cwd=cwd).decode('utf8', 'replace').rstrip()
        except CalledProcessError as e:
            self.log.error("%s Failed: %s", cmd, e)
            self.log.error("Output: %s", out)
            raise
        if out:
            self.log.debug('out> %s', indent(out, ' ' * 5).strip())
        return out
    
    def checkpoint_model(self, checkpoint_id, path):
        if checkpoint_id == '--':
            return dict(
                id=checkpoint_id,
                last_modified=utcnow(),
            )
            
        out = self._git(['log', '-1', '--date=iso', '--format=%ad', checkpoint_id],
            path, include_file=False)
        return dict(
            id = checkpoint_id,
            last_modified = parse_date(out),
        )
    
    def create_checkpoint(self, contents_mgr, path):
        """Create a checkpoint."""
        if not self._in_git(path):
            self.log.warn("Can't create git checkpoint for: %s" % path)
            return super().create_checkpoint(contents_mgr, path)
        diff = self._git('diff', path)
        if not diff.strip():
            self.log.info("Nothing to commit for: %s" % path)
            return self.checkpoint_model('HEAD', path)
        self._git('add', path)
        if not self.create_commits:
            return self.checkpoint_model('--', path)
        basename = path.rsplit('/', 1)[-1]
        self._git(['commit', '-m', 'notebook checkpoint %s' % basename, '-o'],
            path)
        return self.list_checkpoints(path, limit=1)[0]

    def restore_checkpoint(self, contents_mgr, checkpoint_id, path):
        """Restore a checkpoint"""
        self._git(['checkout', checkpoint_id], path=path)

    def rename_checkpoint(self, checkpoint_id, old_path, new_path):
        """On rename, remove the old file from git (no commit)"""
        old_os_path = self._get_os_path(old_path)
        self._git(['rm'], old_os_path)

    def delete_checkpoint(self, checkpoint_id, path):
        """delete a checkpoint for a file"""
        raise RuntimeError("I'm not going to delete git commits")

    def list_checkpoints(self, path, limit=None):
        """Return a list of checkpoints for a given file"""
        limit = limit or self.max_checkpoints
        checkpoints = self._git(['log', '--format=%H', '-%i' % limit], path).split()
        if not self.create_commits:
            # add staging area as a checkpoint if there are staged changes
            out = self._git(['status', '-s'], path)
            if out.strip():
                checkpoints.insert(0, '--')
        return [ self.checkpoint_model(checkpoint_id, path)
            for checkpoint_id in checkpoints
        ]

    def rename_all_checkpoints(self, old_path, new_path):
        """Rename all checkpoints for old_path to new_path."""
        self.rename_checkpoint(None, old_path, new_path)
