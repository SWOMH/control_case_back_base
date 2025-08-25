

class GroupAlreadyExistsException(Exception):
    details = "Group already exists"

class GroupNotFoundException(Exception):
    details = "Group not found"

class UserFoundInGroupException(Exception):
    details = "The user is already a member of this group."

class UserNotInGroupException(Exception):
    details = "User association with group not found"
