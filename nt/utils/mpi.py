"""
Wraps imports for mpi4py to allow code to run on non MPI machines, too.

http://mpi4py.readthedocs.io/en/latest/tutorial.html:
Communication of generic Python objects:
    You have to use all-lowercase ...
Communication of buffer-like objects:
    You have to use method names starting with an upper-case ...

If you want to implement Round-Robin execution, you can try this::
    for example in iterator[RANK::SIZE]:
        pass
"""

import os

__all__ = [
    'RANK',
    'SIZE',
    'MASTER',
    'IS_MASTER',
    'barrier',
    'bcast',
    'gather',
    'map_unordered',
]

_mpi_available = True

try:
    from mpi4py import MPI
    _mpi_available = False
except ImportError:
    import os

    if 'CCS' in os.environ:
        # CCS indicate PC2
        raise

    if int(os.environ.get('OMPI_COMM_WORLD_SIZE', '1')) != 1:
        print(
            f'WARNING: Something is wrong with your mpi4py installation.\n'
            f'Environment size: {os.environ["OMPI_COMM_WORLD_SIZE"]}\n'
            f'mpi4py size: {os.environ["OMPI_COMM_WORLD_SIZE"]}\n'
        )
        raise

    class DUMMY_COMM_WORLD:
        size = 1
        rank = 0
        Barrier = lambda self: None
        bcast = lambda self, data, *args, **kwargs: data
        gather = lambda self, data, *args, **kwargs: [data]

    class _dummy_MPI:
        COMM_WORLD = DUMMY_COMM_WORLD()

    MPI = _dummy_MPI()



class RankInt(int):
    def __bool__(self):
        raise NotImplementedError(
            'Bool is disabled for rank. '
            'It is likely that you want to use IS_MASTER.'
        )


COMM = MPI.COMM_WORLD
RANK = RankInt(COMM.rank)
SIZE = COMM.size
MASTER = RankInt(0)
IS_MASTER = (RANK == MASTER)


def barrier():
    COMM.Barrier()


def bcast(obj, root: int=MASTER):
    return COMM.bcast(obj, root)


def gather(obj, root: int=MASTER):
    return COMM.gather(obj, root=root)


def map_unordered(func, iterator, progress_bar=False):
    """
    A master process push tasks to the workers and receives the result.
    Required at least 2 mpi processes, but to produce a speedup 3 are required.
    Only rank 0 get the results.
    This map is lazy.

    Assume function body is fast.

    Parallel: The execution of func.

    """
    from tqdm import tqdm
    from enum import IntEnum, auto

    if SIZE == 1:
        if progress_bar:
            yield from tqdm(map(func, iterator))
            return
        else:
            yield from map(func, iterator)
            return

    status = MPI.Status()
    workers = SIZE - 1

    class tags(IntEnum):
        """Avoids magic constants."""
        start = auto()
        stop = auto()
        default = auto()

    COMM.Barrier()

    if RANK == 0:
        i = 0
        with tqdm(total=len(iterator), disable=not progress_bar) as pbar:
            pbar.set_description(f'busy: {workers}')
            while workers > 0:
                result = COMM.recv(
                    source=MPI.ANY_SOURCE,
                    tag=MPI.ANY_TAG,
                    status=status)
                if status.tag == tags.default:
                    COMM.send(i, dest=status.source)
                    yield result
                    i += 1
                    pbar.update()
                elif status.tag == tags.start:
                    COMM.send(i, dest=status.source)
                    i += 1
                    pbar.update()
                elif status.tag == tags.stop:
                    workers -= 1
                    pbar.set_description(f'busy: {workers}')
                else:
                    raise ValueError(status.tag)

        assert workers == 0
    else:
        try:
            COMM.send(None, dest=0, tag=tags.start)
            next_index = COMM.recv(source=0)
            for i, val in enumerate(iterator):
                if i == next_index:
                    result = func(val)
                    COMM.send(result, dest=0, tag=tags.default)
                    next_index = COMM.recv(source=0)
        finally:
            COMM.send(None, dest=0, tag=tags.stop)
