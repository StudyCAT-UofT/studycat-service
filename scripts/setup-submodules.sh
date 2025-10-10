# init/update submodules
git submodule update --init --recursive

# apply sparse checkout for the studycat submodule so that only the prisma directory is checked out
git -C external/studycat sparse-checkout init --cone
git -C external/studycat sparse-checkout set prisma