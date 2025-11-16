package com.painkiller;

import static org.junit.jupiter.api.Assertions.assertEquals;
import org.junit.jupiter.api.Test;

public class AdderTest {
    @Test
    public void testAdd() {
        assertEquals(5, Adder.add(2, 3));
    }
}
