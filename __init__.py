from maya import cmds


def lockTransform(node):
    cmds.setAttr(node + ".translate", lock=True)
    cmds.setAttr(node + ".rotate", lock=True)
    cmds.setAttr(node + ".scale", lock=True)
    cmds.lockNode(node, lock=True)


def unlockTransform(node):
    cmds.lockNode(node, lock=False)
    cmds.setAttr(node + ".translate", lock=False)
    cmds.setAttr(node + ".rotate", lock=False)
    cmds.setAttr(node + ".scale", lock=False)


def shortName(node):
    """
    |Original|Pillar ===>>> "Original","Pillar"
    """

    return node.rsplit("|", 1)[-1]


def addIdentifier(node, identifier):
    if cmds.objExists(node + ".identifier"):
        cmds.deleteAttr(node, attribute="identifier")
    cmds.addAttr(node, longName='identifier', shortName="id", dt="string")
    cmds.setAttr(node + '.id', identifier, type="string")


def initializeOriginal():
    """
    Given 1 selected transform, converts it to an "Original" object in the layout tools.

    - Add (hidden) locators to maintain space after freeze transform
    -Parent it to a group names "Originals"
    -Add an "Identifier" attribute containing the transform's name
    (after renaming this may be wrong, but we can still track which object is which)
    - Lock attributes and nose so they can not be changed by the user.
    """
    cmds.undoInfo(openChunk=True)
    originalSelection = cmds.ls(sl=True)

    # IMPORTANT THINGS: try:, except: with raise when error happens,else:, finally:

    try:
        selection = cmds.ls(sl=True, type="transform")
        if not selection or len(selection) != 1:
            cmds.error("Please select exactly 1 object.")

        # Make locators representing the local space
        zero = cmds.parent(cmds.spaceLocator(name="Zero"), selection[0])[0]
        X = cmds.parent(cmds.spaceLocator(name="X"), selection[0])[0]
        Y = cmds.parent(cmds.spaceLocator(name="Y"), selection[0])[0]
        Z = cmds.parent(cmds.spaceLocator(name="Z"), selection[0])[0]
        cmds.setAttr(X + '.translate', 1, 0, 0)
        cmds.setAttr(Y + '.translate', 0, 1, 0)
        cmds.setAttr(Z + '.translate', 0, 0, 1)
        cmds.hide((zero, X, Y, Z))

        # Ensure originals group exists
        if not cmds.objExists("|Originals"):
            originals = cmds.group(em=True, name="Originals")
            lockTransform(originals)
            cmds.hide(originals)

        # Parent the original
        selection = cmds.parent(selection, "|Originals")

        # Add identifier
        addIdentifier(selection[0], shortName(selection[0]))

        # Lock the original
        lockTransform(selection[0])

        # Instantiate the original so we have a workable copy
        instantiateOriginal()

    # If something goes wrong
    except:
        cmds.undoInfo(closeChunk=True)
        # cmds.undo()
        raise
    # if something goes right
    else:
        cmds.undoInfo(closeChunk=True)


def instantiateOriginal(original=None):
    cmds.undoInfo(openChunk=True)
    try:
        if original is None:
            selection = cmds.ls("|Originals|*", sl=True, type="transform")
            if not selection or len(selection) != 1:
                cmds.error("Please select exactly 1 object.")
            original = selection[0]

        copy = cmds.duplicate(original)[0]
        unlockTransform(copy)
        copy = cmds.parent(copy, w=True)
    except:
        cmds.undoInfo(closeChunk=True)
        cmds.undo()
        raise
    else:
        cmds.undoInfo(closeChunk=True)
    return copy


def findOriginal(identifier):
    originals = cmds.ls("|Originals|*.identifier", l=True)
    for original in originals:
        if cmds.getAttr(original) == identifier:
            return original.split(".", 1)[0]


def matrixFromLocators(node):
    row0 = cmds.xform(node + "|X", q=True, ws=True, rp=True)
    row1 = cmds.xform(node + "|Y", q=True, ws=True, rp=True)
    row2 = cmds.xform(node + "|Z", q=True, ws=True, rp=True)
    row3 = cmds.xform(node + "|Zero", q=True, ws=True, rp=True)
    row0[0] -= row3[0]
    row0[1] -= row3[1]
    row0[2] -= row3[2]
    row1[0] -= row3[0]
    row1[1] -= row3[1]
    row1[2] -= row3[2]
    row2[0] -= row3[0]
    row2[1] -= row3[1]
    row2[2] -= row3[2]
    row0 += [0.0]
    row1 += [0.0]
    row2 += [0.0]
    row3 += [0.0]
    return row0 + row1 + row2 + row3


def updateOriginalAndInstances():
    ## Update Original
    # Validate the selection
    selection = cmds.ls(sl=True, type="transform")
    if not selection or len(selection) != 2:
        cmds.error("Please select the new and then the old object.")
    if not cmds.objExists(selection[1] + ".identifier"):
        cmds.error("Please select the new and then the old object."
                   "The old object is missing the identifier attribute, "
                   "did you select in the wrong order?")

    # Get the new and old objects
    new = cmds.duplicate(selection[0])[0]
    identifier = cmds.getAttr(selection[1] + ".identifier")
    old = findOriginal(identifier)
    if old is None:
        cmds.error("Unexpected error, could not find original object with %s." % identifier)
    # Copy the position to new
    oldMatrix = cmds.xform(old, q=True, ws=True, m=True)
    cmds.xform(new, ws=True, m=oldMatrix)
    # Move the locators to new
    for locator in old + "|Zero", old + "|X", old + "|Y", old + "|Z":
        cmds.parent(locator, new)
    # Add the identifier to the new original
    addIdentifier(new, identifier)
    # Delete old
    unlockTransform(old)
    cmds.delete(old)
    # Rename new, parent it to the same parent, lock it, so it completely replaces old
    new = cmds.parent(new, '|Originals')
    new = cmds.rename(new, shortName(old))
    lockTransform(new)

    ## Update Instances
    # Find all object with an identifier
    for instance in cmds.ls("*.identifier", l=True):
        # Do not replace originals, only instances
        if instance.startswith("|Originals|"):
            continue
        # Do not replace objects with the wrong identifier
        if cmds.getAttr(instance) != identifier:
            continue
        # Move a copy to the right place
        copy = instantiateOriginal(new)
        instance = instance.split(".", 1)[0]
        matrix = matrixFromLocators(instance)
        cmds.xform(copy, ws=True, m=matrix)
        # Delete the old instance
        cmds.delete(instance)
        # Steal it's parent name
        ## "|'A'|'B'|'C'"  ====>>> "|A|B",'C'
        parent, old_name = instance.rsplit("|", 1)
        if parent:
            copy = cmds.parent(copy, parent)
        copy = cmds.rename(copy, old_name)
