#!/bin/env python3
import requests
from getpass import getpass
import json
import os
from pathlib import Path


class Seafile:
    def __init__(self, host):
        """
        Constructor
        Logon is also done here
        """
        self.host = host
        self.baseurl = "https://" + host
        self.apitoken = None
        # check local token or login
        self.sf_get_localtoken()

    def sf_admin_get_all_repos(self):
        _api_entry = "/api/v2.1/admin/libraries/?page=1&per_page=100"
        _api_header = {
            "Authorization": "Token " + self.apitoken,
            "Accept": "application/json; indent=4",
        }

        repos = json.loads(self.sf_do_request("get", _api_entry, None, _api_header))

        _repo_sorted = []
        for repo in repos["repos"]:
            _repo_temp = {
                "id": repo["id"],
                "name": repo["name"],
                "owner_name": repo["owner_name"],
                "owner": repo["owner"],
                "encrypted": repo["encrypted"],
                "file_count": repo["file_count"],
                "size": repo["size"],
            }
            _repo_sorted.append(_repo_temp)

        return _repo_sorted

    def sf_admin_get_all_accounts(self):
        _api_entry = "/api2/accounts/"
        _api_header = {
            "Authorization": "Token " + self.apitoken,
            "Accept": "application/json; indent=4",
        }

        _accounts = []

        # scope for LDAP
        _accounts_LDAP = json.loads(
            self.sf_do_request("get", _api_entry, None, _api_header)
        )
        # change scope to local DB
        _api_entry = _api_entry + "?scope=DB&limit=-1"
        _accounts_DB = json.loads(
            self.sf_do_request("get", _api_entry, None, _api_header)
        )

        cnt = 0
        for _ in _accounts_LDAP:
            _accounts.append(_accounts_DB[cnt]["email"])
            cnt += 1
        cnt = 0
        for _ in _accounts_DB:
            _accounts.append(_accounts_DB[cnt]["email"])

        return _accounts

    def sf_admin_get_account_info(self, email):
        _api_entry = "/api2/accounts/" + email + "/"
        _api_header = {
            "Authorization": "Token " + self.apitoken,
            "Accept": "application/json; indent=4",
        }

        _accounts_info = self.sf_do_request("get", _api_entry, None, _api_header)
        return _accounts_info

    def sf_admin_get_shared_links(self, repotoken):
        _api_entry = "/api/v2.1/admin/share-links/" + repotoken + "/"
        _api_header = {
            "Authorization": "Token " + self.apitoken,
            "Accept": "application/json; indent=4",
        }

        _links = json.loads(self.sf_do_request("get", _api_entry, None, _api_header))
        return _links

    def sf_create_dlink(self, repo, path, password=None, expires=None):
        # returns link only
        _repo = repo
        _path = path
        _password = password
        _expires = expires

        _api_entry = "/api/v2.1/share-links/"
        _api_header = {
            "Authorization": "Token " + self.apitoken,
            "Accept": "application/json; indent=4",
        }

        # get repo id
        _repoid = self.sf_get_repoid(_repo)

        _api_data = {"path": _path, "repo_id": _repoid}

        # password
        if password:
            # ToDo: password check
            _api_data["password"] = _password

        if expires:
            _api_data["expire_days"] = expires

        print(_api_data)
        # do sharing
        _link = json.loads(
            self.sf_do_request("post", _api_entry, _api_data, _api_header)
        )
        return _link["link"]

    def sf_create_ulink(self, _repo, path, **kargs):
        pass

    def sf_del_link(self, token):

        # create request
        _api_entry = "/api/v2.1/share-links/" + token
        _api_header = {
            "Authorization": "Token " + self.apitoken,
        }

        success = self.sf_do_request("delete", _api_entry, None, _api_header)
        return success

    def sf_do_request(self, method, api_entry, data, headers):
        _url = self.baseurl + api_entry
        try:
            if headers == "None":
                return requests.request(method.lower(), _url, data=data).text
            else:
                return requests.request(
                    method.lower(), _url, data=data, headers=headers
                ).text

        except TimeoutError:
            print("Connection timed out")
            exit()

    def sf_get_links(self):
        _api_entry = "/api/v2.1/share-links/"
        _api_header = {
            "Authorization": "Token " + self.apitoken,
            "Accept": "application/json; charset=utf-8; indent=4",
        }

        _json = json.loads(self.sf_do_request("get", _api_entry, None, _api_header))
        return _json

    def sf_get_orphaned_links(self):

        _orphaned = {}
        # first get all links
        _links = self.sf_get_links()

        for _link in _links:
            if _link["is_expired"]:
                _link_id = _link["token"]
                _link_properties = (
                    _link["repo_name"] + _link["path"],
                    _link["expire_date"],
                )
                _orphaned[_link_id] = _link_properties

        return _orphaned

    def sf_get_localtoken(self):
        # check os
        if os.name == "nt":
            _tokendir = os.getenv("appdata")
        else:
            _tokendir = os.getenv("HOME") + "/.config"

        _tokendir = _tokendir + "/seafile-python"

        try:
            _tokendir = Path(_tokendir)
            _tokendir.mkdir(exist_ok=True, parents=True)

            # check if token already got and create it if needed.
            _tokenfile = _tokendir.joinpath("apitoken")
            if os.path.isfile(str(_tokenfile)):
                with open(_tokenfile, "r") as f:
                    self.apitoken = str(f.readline())
            else:
                # get token and write it to file
                _apitoken = self.sf_logon()
                with open(_tokenfile, "w") as f:
                    f.write(_apitoken)

        except BaseException as err:
            print("Fehler:", err)

    def sf_get_repoid(self, _repo):
        _api_entry = "/api2/repos/?nameContains=" + _repo
        _api_header = {"Authorization": "Token " + self.apitoken}

        _lib = json.loads(self.sf_do_request("get", _api_entry, None, _api_header))
        _repo_id = _lib[0]["id"]
        return _repo_id

    def sf_search(self, string):
        _api_entry = "/api2/search/?q=" + string + "&search_repo=all"
        _api_header = {"Authorization": "Token " + self.apitoken}

        return self.sf_do_request("get", _api_entry, None, _api_header)

    def sf_logon(self):
        if self.apitoken is None:
            _username = input("Please enter your username: ")
            _password = getpass("Please enter your password: ")

            # build request
            _api_entry = "/api2/auth-token/"

            _api_data = {"username": _username, "password": _password}

            # do request
            _apitoken = json.loads(
                self.sf_do_request("post", _api_entry, _api_data, None)
            )

            # 2 factor authentication
            if "Two factor auth token is missing." in str(_apitoken):
                _otp_token = input("Please enter 2-factor OTP Code:")

                _api_header = {"X-SEAFILE-OTP": _otp_token}

                _apitoken = json.loads(
                    self.sf_do_request("post", _api_entry, _api_data, _api_header)
                )

            try:
                if "<!DOCTYPE html>" in str(_apitoken):
                    raise SystemError("Error in URL Encoding")
                else:
                    self.apitoken = _apitoken["token"]
                    return self.apitoken
            except SystemError:
                print("Error in URL Encoding")
                quit()
