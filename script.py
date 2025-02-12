import System
from Autodesk.Revit.DB import ImportInstance, Category, GeometryInstance, Transform, Options, StorageType, \
    BuiltInCategory, ElementCategoryFilter, FilteredElementCollector, FamilySymbol, ViewPlan, ViewSection, XYZ, \
    Transaction, ElementId
from pyrevit import script
from collections import defaultdict
from System.Windows.Forms import Form, Label, ComboBox, Button, TextBox, DialogResult, FormStartPosition
from System.Drawing import Brushes


def get_revit_version(doc):
    try:
        app = __revit__.Application
        version = app.VersionNumber
        return version
    except Exception as e:
        script.get_output().print_md("Error retrieving Revit version: " + str(e))
        return None

def extract_type_name_from_instance_2023(geometry_instance, output):
    type_name_parameter = None
    try:
        if geometry_instance.Symbol:
            for param in geometry_instance.Symbol.Parameters:
                if param.Definition.Name == "Type Name" and param.StorageType == StorageType.String:
                    type_name_parameter = param.AsString()
                    break
        return type_name_parameter if type_name_parameter else None
    except Exception as e:
        output.print_md("Error extracting 'Type Name' parameter (2023): " + str(e))
        return None

def extract_type_name_from_instance_2024(geometry_instance, output):
    type_name_parameter = None
    try:
        symbol = geometry_instance.GetSymbolGeometryId()
        symbol_id = symbol.SymbolId

        if symbol_id != ElementId.InvalidElementId:
            family_symbol = doc.GetElement(symbol_id)
            if family_symbol:
                for param in family_symbol.Parameters:
                    if param.Definition.Name == "Type Name" and param.StorageType == StorageType.String:
                        type_name_parameter = param.AsString()
                        break
            if type_name_parameter:
                return type_name_parameter
            else:
                return None
        else:
            output.print_md("Error: Invalid SymbolId for GeometryInstance")
            return None
    except Exception as e:
        output.print_md("Error extracting 'SymbolId' and 'Type Name': " + str(e))
        return None

def print_type_name_groups(output, type_name_groups):
    try:
        type_name_list = []
        type_name_map = {}
        for original_type_name in type_name_groups.keys():
            display_type_name = original_type_name.split(".dwg.")[-1]
            type_name_list.append(display_type_name)
            type_name_map[display_type_name] = original_type_name

        selected_type_name_display = forms.SelectFromList.show(type_name_list, title="Select a Type Name",
                                                               multiselect=False)
        if selected_type_name_display:
            selected_type_name = type_name_map[selected_type_name_display]
            return selected_type_name
        else:
            return None
    except Exception as e:
        output.print_md("Error printing Type Name groups: " + str(e))
        return None

def get_import_transform(element):
    try:
        if isinstance(element, ImportInstance):
            return element.GetTransform()
        return None
    except Exception as e:
        script.get_output().print_md("Error getting import transform: " + str(e))
        return None

def convert_to_revit_coordinates(auto_cad_point, import_transform):
    try:
        if import_transform:
            revit_point = import_transform.OfPoint(auto_cad_point)
            return revit_point
        else:
            script.get_output().print_md("No import transform available.")
            return None
    except Exception as e:
        script.get_output().print_md("Error converting AutoCAD coordinates to Revit: " + str(e))
        return None

def process_nested_geometry_instance(geometry_instance, output, nested_count, type_name_groups,
                                     selected_type_name=None, geometry_data=None, import_transform=None):
    try:
        revit_version = get_revit_version(doc)
        if int(revit_version.split(".")[0]) == 2023:
            type_name = extract_type_name_from_instance_2023(geometry_instance, output)
        else:
            type_name = extract_type_name_from_instance_2024(geometry_instance, output)

        if type_name:
            if selected_type_name and type_name != selected_type_name:
                return
            if type_name not in type_name_groups:
                type_name_groups[type_name] = []
            type_name_groups[type_name].append(geometry_instance.Id)
        instance_geometry = geometry_instance.GetSymbolGeometry()
        if instance_geometry:
            for symbol_geometry in instance_geometry:
                if isinstance(symbol_geometry, GeometryInstance):
                    nested_count[0] += 1
                    process_nested_geometry_instance(symbol_geometry, output, nested_count, type_name_groups,
                                                     selected_type_name, geometry_data, import_transform)

        if geometry_instance.Transform:
            transform = geometry_instance.Transform
            position = transform.Origin
            rotation = transform.BasisX

            converted_position = convert_to_revit_coordinates(position, import_transform)

            geometry_data[geometry_instance.Id] = {'position': converted_position, 'rotation': rotation}

    except Exception as e:
        output.print_md("Error processing nested GeometryInstance: " + str(e))

def get_all_sprinklers(doc):
    try:
        sprinkler_filter = ElementCategoryFilter(BuiltInCategory.OST_Sprinklers)
        sprinkler_symbols = FilteredElementCollector(doc).OfClass(FamilySymbol).WherePasses(sprinkler_filter).ToElements()
        families = {symbol.FamilyName for symbol in sprinkler_symbols}
        return sorted(families)
    except Exception as e:
        script.get_output().print_md("Error retrieving sprinkler families: " + str(e))
        return []

def get_active_view_level(doc):
    try:
        active_view = doc.ActiveView
        if isinstance(active_view, ViewPlan) or isinstance(active_view, ViewSection):
            level = active_view.GenLevel
            if level:
                return level
            else:
                script.get_output().print_md("No level associated with active view.")
                return None
        else:
            script.get_output().print_md("Active view is not a plan or section view.")
            return None
    except Exception as e:
        script.get_output().print_md("Error retrieving active view level: " + str(e))
        return None

def select_sprinkler_family(sprinkler_families):
    try:
        selected_sprinkler = forms.SelectFromList.show(sprinkler_families, title="Select a Sprinkler Family",
                                                       multiselect=False)
        return selected_sprinkler
    except Exception as e:
        script.get_output().print_md("Error selecting sprinkler family: " + str(e))
        return None

def get_sprinkler_family_symbol(doc, selected_sprinkler):
    try:
        sprinkler_symbols = FilteredElementCollector(doc).OfClass(FamilySymbol).WhereElementIsElementType().ToElements()
        for symbol in sprinkler_symbols:
            if symbol.Family.Name == selected_sprinkler:
                return symbol
        return None
    except Exception as e:
        script.get_output().print_md("Error retrieving sprinkler family symbol: " + str(e))
        return None

def format_value(value):
    try:
        if isinstance(value, float):
            return "{:.3f}".format(value)
        else:
            return str(value)
    except Exception as e:
        script.get_output().print_md("Error formatting value: " + str(e))
        return str(value)

def place_family_instance(doc, selected_sprinkler, positions, rotation_angle, active_level, desired_offset):
    if not positions:
        script.get_output().print_md("Error: No valid positions found for sprinkler placement.")
        return 0, []
    placed_instances = 0
    placed_instance_ids = []

    if not active_level:
        script.get_output().print_md("Error: No valid level found to place the instance.")
        return placed_instances, placed_instance_ids
    level_elevation_feet = active_level.Elevation
    level_elevation_mm = level_elevation_feet * 304.8  # Convert feet to millimeters for position adjustments

    if not selected_sprinkler:
        script.get_output().print_md("Error: No valid sprinkler family selected.")
        return placed_instances, placed_instance_ids

    with Transaction(doc, "Place Family Instance") as trans:
        trans.Start()

        for position in positions:
            if position:
                # Apply the offset to the Z-coordinate (or other axis as needed)
                new_location = XYZ(position[0], position[1], (position[2] + desired_offset) / 304.8)
                # Creating the family instance at the adjusted position
                family_instance = doc.Create.NewFamilyInstance(new_location, selected_sprinkler, active_level, 0)

                if family_instance:
                    # Apply rotation if necessary
                    rotation_axis = XYZ(0, 0, 1)  # Assuming rotation around Z-axis
                    rotation_point = family_instance.Location.Point
                    rotation_transform = Transform.CreateRotationAtPoint(rotation_axis, rotation_angle, rotation_point)
                    family_instance.Location.Move(rotation_transform.Origin)

                    placed_instances += 1
                    placed_instance_ids.append(family_instance.Id)
                else:
                    script.get_output().print_md("Failed to place family instance at position: X = {}, Y = {}, Z = {}".format(position[0], position[1], position[2]))
            else:
                script.get_output().print_md("Warning: Invalid position, skipping.")

        trans.Commit()

    return placed_instances, placed_instance_ids


def get_active_view_name(doc):
    try:
        active_view = doc.ActiveView
        return active_view.Name if active_view else "No active view"
    except Exception as e:
        script.get_output().print_md("Error retrieving active view name: " + str(e))
        return "No active view"

class InputForm(Form):
    def __init__(self, doc, active_level_elevation_mm, type_name_groups, sprinkler_families):
        self.Text = "Select Family and Block"
        self.Width = 450
        self.Height = 550
        self.doc = doc
        self.type_name_groups = type_name_groups
        self.sprinkler_families = sprinkler_families
        self.Background = Brushes.LightGray

        self.StartPosition = FormStartPosition.CenterScreen
        self.label1 = Label()
        self.label1.Text = "Select a Block:"
        self.label1.Location = System.Drawing.Point(10, 20)
        self.label1.Width = 200
        self.Controls.Add(self.label1)

        self.block_dropdown = ComboBox()
        self.block_dropdown.Location = System.Drawing.Point(10, 50)
        self.block_dropdown.Width = 400
        self.Controls.Add(self.block_dropdown)

        self.label2 = Label()
        self.label2.Text = "Select a Family:"
        self.label2.Location = System.Drawing.Point(10, 80)
        self.label2.Width = 200
        self.Controls.Add(self.label2)

        self.family_dropdown = ComboBox()
        self.family_dropdown.Location = System.Drawing.Point(10, 110)
        self.family_dropdown.Width = 400
        self.Controls.Add(self.family_dropdown)

        self.label3 = Label()
        self.label3.Text = "Enter the offset value (mm):"
        self.label3.Location = System.Drawing.Point(10, 140)
        self.label3.Width = 200
        self.Controls.Add(self.label3)

        self.textbox = TextBox()
        self.textbox.Location = System.Drawing.Point(10, 170)
        self.textbox.Width = 400
        self.Controls.Add(self.textbox)

        self.label4 = Label()
        self.label4.Text = "Active View and Elevation (mm):"
        self.label4.Location = System.Drawing.Point(10, 200)
        self.label4.Width = 200
        self.Controls.Add(self.label4)

        self.elevation_textbox = TextBox()
        self.elevation_textbox.Location = System.Drawing.Point(10, 230)
        self.elevation_textbox.Width = 400
        self.elevation_textbox.ReadOnly = True
        self.elevation_textbox.Text = "{} ({})".format(str(get_active_view_name(doc)), active_level_elevation_mm)
        self.Controls.Add(self.elevation_textbox)

        self.button = Button()
        self.button.Text = "Submit"
        self.button.Location = System.Drawing.Point(10, 260)
        self.button.Click += self.on_submit
        self.Controls.Add(self.button)

        self.load_families()
        self.load_blocks()

        self.result = None

    def load_blocks(self):
        block_names = list(self.type_name_groups.keys())
        display_block_names = []
        self.block_name_map = {}

        for block_name in block_names:
            display_block_name = block_name.split(".dwg.")[-1]
            display_block_names.append(display_block_name)
            self.block_name_map[display_block_name] = block_name

        for display_block_name in display_block_names:
            self.block_dropdown.Items.Add(display_block_name)

    def load_families(self):
        for family in self.sprinkler_families:
            self.family_dropdown.Items.Add(family)

    def on_submit(self, sender, event):
        try:
            self.selected_block_display_name = self.block_dropdown.SelectedItem
            self.selected_block = self.block_name_map.get(self.selected_block_display_name, None)
            self.selected_family = self.family_dropdown.SelectedItem
            self.offset_value = float(self.textbox.Text)
            self.DialogResult = DialogResult.OK
        except ValueError:
            self.selected_block = None
            self.selected_family = None
            self.offset_value = None
        self.Close()


doc = __revit__.ActiveUIDocument.Document
output = script.get_output()


selected_ids = __revit__.ActiveUIDocument.Selection.GetElementIds()

active_level = get_active_view_level(doc)
revit_version = doc.Application.VersionName

if active_level:
    level_elevation = active_level.Elevation
    level_elevation_mm = level_elevation * 304.8
else:
    output.print_md("No active level found.")

if not selected_ids:
    output.print_md("No elements selected. Please select a linked CAD file.")
else:
    found_cad_file = False
    type_name_groups = defaultdict(list)
    geometry_data = {}

    for elem_id in selected_ids:
        element = doc.GetElement(elem_id)
        if isinstance(element, ImportInstance):
            found_cad_file = True
            cad_file_id = element.Id

            import_transform = get_import_transform(element)

            geo_options = Options()
            geometry_element = element.get_Geometry(geo_options)

            if geometry_element:
                nested_count = [0]
                for geometry_obj in geometry_element:
                    if isinstance(geometry_obj, GeometryInstance):
                        process_nested_geometry_instance(geometry_obj, output, nested_count, type_name_groups, geometry_data=geometry_data,
                                                         import_transform=import_transform)
            else:
                output.print_md("No geometry data found in the selected linked CAD file.")

    if not found_cad_file:
        output.print_md("No linked CAD file found in the selected elements.")

# Get all sprinkler families
sprinkler_families = get_all_sprinklers(doc)

# Show input form to get user data
form = InputForm(doc, level_elevation_mm, type_name_groups, sprinkler_families)
form.ShowDialog()

# After the form is submitted:
if form.DialogResult == DialogResult.OK:
    # The user provided input
    selected_block = form.selected_block
    selected_family = form.selected_family
    offset_value = form.offset_value  # This is the user-given offset in mm

    output.print_md("Selected Family: " + selected_family)
    output.print_md("Selected Block: " + selected_block)
    output.print_md("Offset Value: " + str(offset_value) + " mm")

    # Retrieve the corresponding sprinkler symbol from the document
    sprinkler_symbol = get_sprinkler_family_symbol(doc, selected_family)
    if not sprinkler_symbol:
        output.print_md("Error: Sprinkler family symbol not found in the document.")
    else:
        output.print_md("Sprinkler family symbol found: {}".format(selected_family))

        # Get the positions based on the selected block and type name
        position = None
        if selected_block:
            position = [geometry_data[geometry_instance_id]['position'] for geometry_instance_id in
                        type_name_groups[selected_block]]

        # Place the family instances in the document
        placed_instances, placed_instance_ids = place_family_instance(doc, sprinkler_symbol, position, 0,
                                                                      active_level,
                                                                      desired_offset=offset_value)  # Pass the user-given offset value here

        output.print_md("Successfully placed {} instances.".format(placed_instances))

else:
    output.print_md("Form was not submitted. Exiting process.")
