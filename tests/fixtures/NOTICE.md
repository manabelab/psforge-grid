# Third-party test data

Files in this directory that did not originate here, with the terms they are
provided under. Keep the notices below with any copy of these files.

Two layers matter for each file and are recorded separately: the terms under
which it was **obtained**, and who created the **model** it contains. A project
can only license what it owns, so a permissive repository holding someone else's
data does not by itself settle the second layer.

---

## 39bus.raw — New England 39-bus system (PSS/E RAW v34)

- **Obtained from**: <https://github.com/NatLabRockies/ParaEMT_public>,
  `models/39bus_psse/39bus.raw`, byte-for-byte unmodified.
- **Terms**: BSD 3-Clause (`LICENSE.md` of that repository), reproduced below.
  The repository states no exception for its data files.
- **Model credit**: the file's own header reads
  `NEW ENGLAND TEST SYSTEM, 39 BUSES, 9 GENERATORS / CREATED BY PABLO LEDESMA
  PABLOLE@ING.UC3M.ES` (Universidad Carlos III de Madrid). That header is the
  attribution and must not be stripped.
- **Why it is here**: it is the only PSS/E **v34** file in this directory, and it
  was written by PSS/E itself (`PSS(R)E-34.8 FRI, DEC 09 2022`). Tests that read
  only files psforge wrote cannot show that psforge reads what other tools
  produce.

```
Copyright (c) Year, Alliance for Sustainable Energy, LLC

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

(The upstream file reads "Copyright (c) Year" — the placeholder was never filled
in. It is reproduced verbatim rather than corrected.)

Clause 3 forbids using the copyright holder's name to promote products derived
from this software: do not describe psforge as endorsed by, or associated with,
Alliance for Sustainable Energy or NREL.

---

## Not yet recorded

The other files in this directory predate this notice and their provenance is
still being settled. They are listed in `README.md` with the URL each came from.
Nothing may be added to this directory until its entry here is written.
