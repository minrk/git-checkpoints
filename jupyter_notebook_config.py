c.FileContentsManager.checkpoints_class = 'gitcheckpoints.GitCheckpoints'
c.NotebookApp.open_browser = False
# toggle for whether create_checkpoint just does `add` or `add & commit`
c.GitCheckpoints.create_commits = False
import logging
c.Application.log_level = logging.DEBUG
