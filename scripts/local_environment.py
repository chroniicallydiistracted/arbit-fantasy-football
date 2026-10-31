"""Create an ignored local-only process profile once; never print secret values."""

import os
import secrets
from pathlib import Path


def initialize(path: Path) -> bool:
    data=(
        '# Local operator profile. Keep private; never use this token in a browser bundle.\n'
        'ARBIT_ENV=development\n'
        'ARBIT_DATABASE_URL=postgresql+psycopg://arbit_local:arbit-local-dev-only@127.0.0.1:55439/arbit_local\n'
        'ARBIT_STORAGE_PATH=data/source-archives\n'
        'ARBIT_OPERATOR_TOKEN='+secrets.token_urlsafe(32)+'\n'
    )
    try:
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor,'w') as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())
    return True


if __name__=='__main__':
    created=initialize(Path('.env.local'))
    print('Created private .env.local' if created else 'Preserved existing .env.local')
