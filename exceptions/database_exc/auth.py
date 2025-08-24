
class UserNotFoundExists(Exception):
    details = "User not found"


class UserAlreadyExistsException(Exception):
    details = "User already exists"


class UserPasswordNotCorrectException(Exception):
    details = "Password not correct"


class UserMailNotCorrectException(Exception):
    details = "A user with this email already exists"


class UserBannedException(Exception):
    details = "Account blocked"


class UserInvalidEmailOrPasswordException(Exception):
    details = "Invalid email or password"


class UserTokenNotFoundException(Exception):
    details = "Token not found in the system"


class UserNotPermissionsException(Exception):
    details = "Invalid access rights"


class UserNotPermissionsException(Exception):
    details = "Invalid access rights"

