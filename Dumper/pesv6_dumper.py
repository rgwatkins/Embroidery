from enum import Enum

class HOOP(Enum):
    SIZE_100x100 = 1
    SIZE_180x130 = 2 
    SIZE_272x272 = 3
    SIZE_408x272 = 4


class PesDumperMixin:

    def version_supported(self, version):
        return version == 60
    
    def get_tagged_string(self):
        tag = self.get_uint24()
        assert tag == 0xFFFEFF
        length = self.get_uint8()
        return(''.join(chr(self.get_uint16()) for _ in range(length)))  # unicode?
        
    def dump_tagged_string(self, id, fmt='"{:s}"'):
        self.print_addr()
        return self.print_result(id, self.get_tagged_string(), fmt)

    def dump_header(self):
        with self.section('PES Header Prologue'):
            pec_offset = self.dump_uint32('pec_offset', fmt='hex')
            n_pecs = self.dump_uint16('n_pecs')
            self.dump_text('hoop_size', 2)
            self.dump_utf8('name')
            self.dump_utf8('category')
            self.dump_utf8('author')
            self.dump_utf8('keywords')
            self.dump_utf8('comments')
            self.dump_bool16('optimize_hoop_change')
            self.dump_bool16('custom_design_page')
            self.dump_uint16('hoop_width')
            self.dump_uint16('hoop_height')
            self.dump_uint16('design_page_area') # doc says "hoop rotation (1=90 degrees)
            self.dump_uint16('design_width')
            self.dump_uint16('design_height')
            self.dump_uint16('section_width')
            self.dump_uint16('section_height')
            self.dump_data('unknown', 2) # doc: must be in same ranges as section width & height 
            self.dump_uint16('background_color')
            self.dump_uint16('foreground_color')
            self.dump_bool16('show_grid')
            self.dump_bool16('with_axes')
            self.dump_bool16('snap_to_grid')
            self.dump_uint16('grid_interval')
            self.dump_data('unknown', 2)
            self.dump_bool16('optimize_entry_exit_points')
            self.dump_utf8('from_image')
            self.dump_vector_float32('transform_matrix', 6)
        return n_pecs, pec_offset

    def dump_thread(self):
        self.dump_tagged_string('catalog_number')
        self.dump_data('color_rgbx', 4)
        self.dump_uint32('color_type')
        self.dump_tagged_string('chart_index') 
        self.dump_tagged_string('thread_brand')
        self.dump_tagged_string('chart_length') # doc says chart_name

    def dump_csewseg_header(self):
        self.dump_vector_int16('extents1', 4)
        self.dump_vector_int16('extents2', 4)
        self.dump_vector_float32('transform_matrix', 6)
        self.dump_data('unknown', 2)
        self.dump_int16('x_coordinate_translation')
        self.dump_int16('y_coordinate_translation')
        self.dump_int16('width')
        self.dump_int16('height')
        self.dump_data('unknown', 8)
        n_blocks = self.dump_uint16('n_blocks')
        assert(self.dump_uint32('end marker', fmt='hex') == 0xFFFF)
        return n_blocks

    def dump_csewseg_stitch_list(self, n_blocks):
        for j in range(n_blocks):
            with self.subsection('Stitch List Block {:d}/{:d}'.format(j+1, n_blocks)):
                self.dump_uint16('stitch_type')
                self.dump_uint16('thread_index')
                ## Coordinates here are absolute. Their deltas coorespond to the stitches
                ## in the PEC section, except that the y-coordinate is first and the
                ## x-coordinate is second.
                n_coordinates = self.dump_uint16('n_coordinates')
                self.tab = 0
                for k in range(n_coordinates):
                    self.dump_vector_int16(None, 2)
                if j < n_blocks-1:
                    self.dump_uint16('continuation_code', fmt='0x{:04x}')
            
    def dump_csewseg_color_list(self):
        with self.subsection('Color List'):
            n_colors = self.dump_uint16('n_colors')
            for i in range(n_colors):
                self.dump_uint16('block_index')
                self.dump_uint16('thread_index')


def dump_pes_data(f):    

    """Dumps the PES section of the file. Should be called with the file positioned
    just after the magic number and version. Leaves the file positioned at the start
    of the PEC data."""

    n_pecs, pec_offset = f.dump_header()

    with f.section('Fill Patterns'):
        assert f.dump_uint16('n_fill_patterns') == 0

    with f.section('Motif Patterns'):
        assert f.dump_uint16('n_motif_patterns') == 0

    with f.section('Feather Patterns'):
        assert f.dump_uint16('n_feather_patterns') == 0

    with f.section('Threads', tab=16):
        nthreads = f.dump_uint16('n_threads')
        f.print()
        for i in range(nthreads):
            with f.subsection('Thread {:d}'.format(i+1)):
                f.dump_thread()

    with f.section('PES Header Epilogue'):
        n_objects = f.dump_uint16('n_objects')
        assert(f.dump_uint32('end marker', fmt='hex') == 0xFFFF) # end of header marker

    with f.section('CEmbOne', tab=26):
        f.dump_utf8('section_id', length_size=2)  # there is always a CEmbOne section
        n_blocks = f.dump_csewseg_header()

    for i in range(n_objects):
        with f.section('CSewSeg #{:d}'.format(i+1), tab=16, hide=not f.show_stitches):
            f.dump_utf8('section_id', length_size=2)
            f.print()
            f.dump_csewseg_stitch_list(n_blocks)
            f.dump_csewseg_color_list()

    excess = pec_offset-f.tell()
    if excess > 0:
        with f.section('Excess ({:d} bytes)'.format(excess), tab=0):
            f.dump_data(None, excess)

    f.seek(pec_offset)
    return n_pecs


if __name__ == '__main__':
    import pes_dump
    pes_dump.main()
        
