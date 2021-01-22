# LiveFireChallenges for CTFd (Need to update readme from the DynamicChallenges one :))

CTFd lacks funcitonality to adequately manage VM based CTF challenges. Vulnerable machines often
need to be reverted to ensure exploitability.

This CTFd plugin creates a livefire challenge type which implements this
behavior. Each challenge must be tied to a VM on a vsphere server that can be
reverted and powered on with the credentials specified at the top of the init file.
The challenge type also stores and displays the last reverted time, for displaying to 
competitors

# Installation

**REQUIRES: CTFd >= v1.2.0**

1. Clone this repository to `CTFd/plugins`. It is important that the folder is
   named `livefire_challenges` so CTFd can serve the files in the `assets`
   directory.
