import os
import pytest

from scriptworker.context import Context
from treescript.exceptions import TaskVerificationError
from treescript.test import tmpdir, is_slice_in_list
from treescript.script import get_default_config
import treescript.versionmanip as vmanip


assert tmpdir  # flake8


@pytest.yield_fixture(scope='function')
def context(tmpdir):
    context = Context()
    context.config = get_default_config()
    context.config['work_dir'] = os.path.join(tmpdir, 'work')
    context.task = {}
    yield context


@pytest.fixture(scope='function',
                # XXX add 52.3.0esr to this set when we support esr here
                params=('52.5.0', '52.0b3', '# foobar\n52.1a3'))
def repo_context(tmpdir, context, request):
    context.repo = os.path.join(tmpdir, 'repo')
    context.xtest_version = request.param
    if '\n' in request.param:
        context.xtest_version = [l
                                 for l in request.param.splitlines()
                                 if not l.startswith("#")][0]
    os.mkdir(context.repo)
    os.mkdir(os.path.join(context.repo, 'config'))
    version_file = os.path.join(context.repo, 'config', 'milestone.txt')
    with open(version_file, 'w') as f:
        f.write(request.param)
    yield context


def test_get_version(repo_context):
    ver = vmanip._get_version(os.path.join(repo_context.repo, 'config', 'milestone.txt'))
    assert ver == repo_context.xtest_version


@pytest.mark.parametrize('new_version', ('87.0', '87.1b3', '123.2esr'))
def test_replace_ver_in_file(repo_context, new_version):
    filepath = os.path.join(repo_context.repo, 'config', 'milestone.txt')
    old_ver = repo_context.xtest_version
    vmanip.replace_ver_in_file(filepath, old_ver, new_version)
    assert new_version == vmanip._get_version(filepath)


@pytest.mark.parametrize('new_version', ('87.0', '87.1b3', '123.2esr'))
def test_replace_ver_in_file_invalid_old_ver(repo_context, new_version):
    filepath = os.path.join(repo_context.repo, 'config', 'milestone.txt')
    old_ver = '45.0'
    with pytest.raises(Exception):
        vmanip.replace_ver_in_file(filepath, old_ver, new_version)


@pytest.mark.asyncio
@pytest.mark.parametrize('new_version', (
    '87.0',
    '87.1b3',
    pytest.param('123.2esr', marks=pytest.mark.xfail)  # XXX 'esr' fails StrictVersion
))
async def test_bump_version(mocker, repo_context, new_version):
    called_args = []

    async def run_command(context, *arguments, local_repo=None):
        called_args.append([tuple([context]) + arguments, {'local_repo': local_repo}])

    relative_files = [os.path.join('config', 'milestone.txt')]
    bump_info = {'files': relative_files, 'next_version': new_version}
    mocked_bump_info = mocker.patch.object(vmanip, 'get_version_bump_info')
    mocked_bump_info.return_value = bump_info
    mocker.patch.object(vmanip, 'run_hg_command', new=run_command)
    await vmanip.bump_version(repo_context)
    assert new_version == vmanip._get_version(
        os.path.join(repo_context.repo, relative_files[0]))
    assert len(called_args) == 1
    assert 'local_repo' in called_args[0][1]
    assert is_slice_in_list(('commit', '-m'), called_args[0][0])


@pytest.mark.asyncio
@pytest.mark.parametrize('new_version', (
    '87.0',
    '87.1b3',
    pytest.param('123.2esr', marks=pytest.mark.xfail)  # XXX 'esr' fails StrictVersion
))
async def test_bump_version_invalid_file(mocker, repo_context, new_version):
    called_args = []

    async def run_command(context, *arguments, local_repo=None):
        called_args.append([tuple([context]) + arguments, {'local_repo': local_repo}])

    relative_files = [os.path.join('config', 'invalid_file.txt'), os.path.join('config', 'milestone.txt')]
    bump_info = {'files': relative_files, 'next_version': new_version}
    mocked_bump_info = mocker.patch.object(vmanip, 'get_version_bump_info')
    mocked_bump_info.return_value = bump_info
    mocker.patch.object(vmanip, 'run_hg_command', new=run_command)
    with pytest.raises(TaskVerificationError):
        await vmanip.bump_version(repo_context)
    assert repo_context.xtest_version == vmanip._get_version(
        os.path.join(repo_context.repo, relative_files[1]))
    assert len(called_args) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('new_version', (
    '87.0',
    '87.1b3',
    pytest.param('123.2esr', marks=pytest.mark.xfail)  # XXX 'esr' fails StrictVersion
))
async def test_bump_version_missing_file(mocker, repo_context, new_version):
    called_args = []

    async def run_command(context, *arguments, local_repo=None):
        called_args.append([tuple([context]) + arguments, {'local_repo': local_repo}])

    # Test only creates config/milestone.txt
    relative_files = [os.path.join('browser', 'config', 'version_display.txt'), os.path.join('config', 'milestone.txt')]
    bump_info = {'files': relative_files, 'next_version': new_version}
    mocked_bump_info = mocker.patch.object(vmanip, 'get_version_bump_info')
    mocked_bump_info.return_value = bump_info
    mocker.patch.object(vmanip, 'run_hg_command', new=run_command)
    with pytest.raises(TaskVerificationError):
        await vmanip.bump_version(repo_context)
    assert repo_context.xtest_version == vmanip._get_version(
        os.path.join(repo_context.repo, relative_files[1]))
    assert len(called_args) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('new_version', (
    '27.0',
    '26.1b3',
    pytest.param('45.2esr', marks=pytest.mark.xfail)  # XXX 'esr' fails StrictVersion
))
async def test_bump_version_smaller_version(mocker, repo_context, new_version):
    called_args = []

    async def run_command(context, *arguments, local_repo=None):
        called_args.append([tuple([context]) + arguments, {'local_repo': local_repo}])

    relative_files = [os.path.join('config', 'milestone.txt')]
    bump_info = {'files': relative_files, 'next_version': new_version}
    mocked_bump_info = mocker.patch.object(vmanip, 'get_version_bump_info')
    mocked_bump_info.return_value = bump_info
    mocker.patch.object(vmanip, 'run_hg_command', new=run_command)
    await vmanip.bump_version(repo_context)
    assert repo_context.xtest_version == vmanip._get_version(
        os.path.join(repo_context.repo, relative_files[0]))
    assert len(called_args) == 0


@pytest.mark.asyncio
async def test_bump_version_same_version(mocker, repo_context):
    called_args = []

    async def run_command(context, *arguments, local_repo=None):
        called_args.append([tuple([context]) + arguments, {'local_repo': local_repo}])

    relative_files = [os.path.join('config', 'milestone.txt')]
    bump_info = {'files': relative_files, 'next_version': repo_context.xtest_version}
    mocked_bump_info = mocker.patch.object(vmanip, 'get_version_bump_info')
    mocked_bump_info.return_value = bump_info
    mocker.patch.object(vmanip, 'run_hg_command', new=run_command)
    await vmanip.bump_version(repo_context)
    assert repo_context.xtest_version == vmanip._get_version(
        os.path.join(repo_context.repo, relative_files[0]))
    assert len(called_args) == 0
