#!/usr/bin/python
#
# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import os
import config
import shutil

from utils import Base
from utils import set_private_key
from utils import ManageSfUtils
from utils import GerritGitUtils
from utils import create_random_str
from utils import GerritUtil


class TestGerrit(Base):
    """ Functional tests that validate some gerrit behaviors.
    """
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.projects = []
        self.clone_dirs = []
        self.dirs_to_delete = []
        self.msu = ManageSfUtils(config.MANAGESF_HOST, 80)

    def tearDown(self):
        for name in self.projects:
            self.msu.deleteProject(name,
                                   config.ADMIN_USER)
        for dirs in self.dirs_to_delete:
            shutil.rmtree(dirs)

    def createProject(self, name, options=None):
        self.msu.createProject(name,
                               config.ADMIN_USER,
                               options=options)
        self.projects.append(name)

    def test_add_remove_user_in_core_as_admin(self):
        """ Add/remove user from core group as admin
        """
        gu = GerritUtil(config.GERRIT_SERVER, username=config.ADMIN_USER)
        pname = 'p_%s' % create_random_str()
        self.createProject(pname)
        assert gu.isPrjExist(pname)
        NEW_USER = 'user2'
        GROUP_NAME = '%s-core' % pname
        assert gu.isGroupExist(GROUP_NAME)
        assert not gu.isMemberInGroup(NEW_USER, GROUP_NAME)
        gu.addGroupMember(NEW_USER, GROUP_NAME)
        assert gu.isMemberInGroup(NEW_USER, GROUP_NAME)
        gu.deleteGroupMember(NEW_USER, GROUP_NAME)
        assert not gu.isMemberInGroup(NEW_USER, GROUP_NAME)

    def test_add_remove_user_in_ptl_as_admin(self):
        """ Add/remove user from ptl group as admin
        """
        gu = GerritUtil(config.GERRIT_SERVER, username=config.ADMIN_USER)
        pname = 'p_%s' % create_random_str()
        self.createProject(pname)
        assert gu.isPrjExist(pname)
        NEW_USER = 'user2'
        GROUP_NAME = '%s-ptl' % pname
        assert gu.isGroupExist(GROUP_NAME)
        assert not gu.isMemberInGroup(NEW_USER, GROUP_NAME)
        gu.addGroupMember(NEW_USER, GROUP_NAME)
        assert gu.isMemberInGroup(NEW_USER, GROUP_NAME)
        gu.deleteGroupMember(NEW_USER, GROUP_NAME)
        assert not gu.isMemberInGroup(NEW_USER, GROUP_NAME)

    def test_review_labels(self):
        """ Test if list of review labels are as expected
        """
        pname = 'p_%s' % create_random_str()
        self.createProject(pname)
        un = config.ADMIN_USER
        gu = GerritUtil(config.GERRIT_SERVER, username=un)
        k_index = gu.addPubKey(config.USERS[un]["pubkey"])
        assert gu.isPrjExist(pname)
        priv_key_path = set_private_key(config.USERS[un]["privkey"])
        gitu = GerritGitUtils(un,
                              priv_key_path,
                              config.USERS[un]['email'])
        url = "ssh://%s@%s/%s" % (un, config.GERRIT_HOST,
                                  pname)
        clone_dir = gitu.clone(url, pname)
        self.dirs_to_delete.append(os.path.dirname(clone_dir))

        gitu.add_commit_and_publish(clone_dir, "master", "Test commit")

        change_ids = gu.getMyChangesForProject(pname)
        self.assertEqual(len(change_ids), 1)
        change_id = change_ids[0]

        url = '/a/changes/%s/?o=LABELS' % change_id
        labels = gu.rest.get(url)['labels']

        self.assertIn('Approved', labels)
        self.assertIn('Code-Review', labels)
        self.assertIn('Verified', labels)
        self.assertEqual(len(labels.keys()), 3)

        gu.delPubKey(k_index)

    def test_review_submit_approval(self):
        """ Test submit criteria - CR(2 +2s), V(+1), A(+1)
        """
        pname = 'p_%s' % create_random_str()
        options = {'core-group': 'user2'}
        self.createProject(pname, options)
        un = config.ADMIN_USER
        gu = GerritUtil(config.GERRIT_SERVER, username=un)
        k_index = gu.addPubKey(config.USERS[un]["pubkey"])
        assert gu.isPrjExist(pname)
        priv_key_path = set_private_key(config.USERS[un]["privkey"])
        gitu = GerritGitUtils(un,
                              priv_key_path,
                              config.USERS[un]['email'])
        url = "ssh://%s@%s/%s" % (un, config.GERRIT_HOST,
                                  pname)
        clone_dir = gitu.clone(url, pname)
        self.dirs_to_delete.append(os.path.dirname(clone_dir))

        gitu.add_commit_and_publish(clone_dir, "master", "Test commit")

        change_ids = gu.getMyChangesForProject(pname)
        self.assertEqual(len(change_ids), 1)
        change_id = change_ids[0]

        gu.setPlus1CodeReview(change_id, "current")
        self.assertEqual(gu.submitPatch(change_id, "current"), 409)

        gu.setPlus1Verified(change_id, "current")
        self.assertEqual(gu.submitPatch(change_id, "current"), 409)

        gu.setPlus1Approved(change_id, "current")
        self.assertEqual(gu.submitPatch(change_id, "current"), 409)

        gu.setPlus2CodeReview(change_id, "current")
        self.assertEqual(gu.submitPatch(change_id, "current"), 409)

        gu_user2 = GerritUtil(config.GERRIT_SERVER, username=config.USER_2)
        gu_user2.setPlus2CodeReview(change_id, "current")
        self.assertEqual(
            gu.submitPatch(change_id, "current")['status'], 'MERGED')
        gu.delPubKey(k_index)

    def test_ifexist_download_commands(self):
        """ Test if download-commands plugin is present
        """
        gu = GerritUtil(config.GERRIT_SERVER, username=config.ADMIN_USER)
        plugins = gu.listPlugins()
        self.assertIn('download-commands', plugins)

    def test_ifexist_gravatar(self):
        """ Test if gravatar plugin is present
        """
        gu = GerritUtil(config.GERRIT_SERVER, username=config.ADMIN_USER)
        plugins = gu.listPlugins()
        self.assertIn('gravatar-avatar-provider', plugins)

    def test_ifexist_reviewers_by_blame(self):
        """ Test if reviewers-by-blame plugin is present
        """
        gu = GerritUtil(config.GERRIT_SERVER, username=config.ADMIN_USER)
        plugins = gu.listPlugins()
        self.assertIn('reviewers-by-blame', plugins)

    def test_check_download_commands(self):
        """ Test if download commands plugin works
        """
        pname = 'p_%s' % create_random_str()
        self.createProject(pname)
        un = config.ADMIN_USER
        gu = GerritUtil(config.GERRIT_SERVER, username=un)
        assert gu.isPrjExist(pname)
        k_index = gu.addPubKey(config.USERS[un]["pubkey"])
        priv_key_path = set_private_key(config.USERS[un]["privkey"])
        gitu = GerritGitUtils(un,
                              priv_key_path,
                              config.USERS[un]['email'])
        url = "ssh://%s@%s/%s" % (un, config.GERRIT_HOST,
                                  pname)
        clone_dir = gitu.clone(url, pname)
        self.dirs_to_delete.append(os.path.dirname(clone_dir))

        gitu.add_commit_and_publish(clone_dir, "master", "Test commit")

        change_ids = gu.getMyChangesForProject(pname)
        self.assertEqual(len(change_ids), 1)
        change_id = change_ids[0]
        resp = gu.rest.get('/a/changes/%s/?o=CURRENT_REVISION' % change_id)
        self.assertIn("current_revision", resp)
        self.assertIn("revisions", resp)

        current_rev = resp["current_revision"]

        fetch = resp["revisions"][current_rev]["fetch"]
        self.assertGreater(fetch.keys(), 0)

        # disable and check if the fetch has anything
        gu.disablePlugin("download-commands")
        resp = gu.rest.get('/a/changes/%s/?o=CURRENT_REVISION' % change_id)
        fetch = resp["revisions"][current_rev]["fetch"]
        self.assertEqual(len(fetch.keys()), 0)

        # enable the plugin and check if the fetch information is valid
        gu.enablePlugin("download-commands")
        resp = gu.rest.get('/a/changes/%s/?o=CURRENT_REVISION' % change_id)
        fetch = resp["revisions"][current_rev]["fetch"]
        self.assertGreater(len(fetch.keys()), 0)

        gu.delPubKey(k_index)

    def test_check_add_automatic_reviewers(self):
        """ Test if reviewers-by-blame plugin works
        """
        pname = 'p_%s' % create_random_str()
        options = {'core-group': 'user2'}
        self.createProject(pname, options)
        first_u = config.ADMIN_USER
        gu_first_u = GerritUtil(config.GERRIT_SERVER, username=first_u)
        assert gu_first_u.isPrjExist(pname)
        # Push data in the create project as Admin user
        k1_index = gu_first_u.addPubKey(config.USERS[first_u]["pubkey"])
        priv_key_path = set_private_key(config.USERS[first_u]["privkey"])
        gitu = GerritGitUtils(first_u,
                              priv_key_path,
                              config.USERS[first_u]['email'])
        url = "ssh://%s@%s/%s" % (first_u, config.GERRIT_HOST,
                                  pname)
        clone_dir = gitu.clone(url, pname)
        self.dirs_to_delete.append(os.path.dirname(clone_dir))
        data = ['this', 'is', 'a', 'couple', 'of', 'lines']
        clone_dir = gitu.clone(url, pname)
        gitu.add_commit_and_publish(clone_dir, "master", "Test commit",
                                    fname="file",
                                    data="\n".join(data))
        # Get the change id
        change_ids = gu_first_u.getMyChangesForProject(pname)
        self.assertEqual(len(change_ids), 1)
        change_id = change_ids[0]
        # Merge the change
        gu_first_u.setPlus2CodeReview(change_id, "current")
        gu_first_u.setPlus1Verified(change_id, "current")
        gu_first_u.setPlus1Approved(change_id, "current")
        second_u = config.USER_2
        gu_second_u = GerritUtil(config.GERRIT_SERVER, username=second_u)
        gu_second_u.setPlus2CodeReview(change_id, "current")
        self.assertEqual(
            gu_first_u.submitPatch(change_id, "current")['status'], 'MERGED')
        # Change the file we have commited with Admin user
        k2_index = gu_second_u.addPubKey(config.USERS[second_u]["pubkey"])
        priv_key_path = set_private_key(config.USERS[second_u]["privkey"])
        gitu = GerritGitUtils(second_u,
                              priv_key_path,
                              config.USERS[second_u]['email'])
        url = "ssh://%s@%s/%s" % (second_u, config.GERRIT_HOST,
                                  pname)
        clone_dir = gitu.clone(url, pname)
        self.dirs_to_delete.append(os.path.dirname(clone_dir))
        data = ['this', 'is', 'some', 'lines']
        gitu.add_commit_and_publish(clone_dir, "master", "Test commit",
                                    fname="file",
                                    data="\n".join(data))
        # Get the change id
        change_ids = gu_second_u.getMyChangesForProject(pname)
        self.assertEqual(len(change_ids), 1)
        change_id = change_ids[0]
        # Verify first_u has been automatically added to reviewers
        reviewers = gu_second_u.getReviewers(change_id)
        self.assertEqual(len(reviewers), 1)
        self.assertEqual(reviewers[0], first_u)

        gu_first_u.delPubKey(k1_index)
        gu_second_u.delPubKey(k2_index)